import os
import datetime
import hashlib
from datetime import timedelta

import psycopg2
from flask import Flask, render_template, url_for, redirect, request, session
from flask_selfdoc import Autodoc
from psycopg2 import Error
from flask_wtf.csrf import CSRFProtect
from PIL import Image



#port = int(os.getenv("PORT"))
salt = os.urandom(32)
app=Flask(__name__)
auto = Autodoc(app)
app.permanent_session_lifetime=timedelta(minutes=60)

csrf = CSRFProtect(app)
SESSION_COOKIE_SECURE = True
REMEMBER_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_HTTPONLY = True
app.secret_key="Tajemny"


def generate_heshlib_key(password1,salt1):
    """ Funkcja hashujaca haslo password1 100000 razy przy pomocy sha256 z zadanym ziarnem salt1 """
    key = hashlib.pbkdf2_hmac(
            'sha256',
            password1.encode('utf-8'),
            salt1,
            100000
    )
    return key


#próba połączenia się z bazą
try:
    connection = psycopg2.connect("dbname='sijiwwtg' user='sijiwwtg' host='rajje.db.elephantsql.com' password='Vcl29BwW9XCH5xNis4X2fw-zao-ubmns'")
except (Exception, Error) as error:
    print("Error while connecting to PostgreSQL", error)


@auto.doc()
def is_user_admin(id_user):
    """ Funkcja autoryzująca użytkownika - zwraca True jeśli użytkownik o id_user ma w bazie uprawnienia administratora, w przeciwnym przypadku False"""
    cursor = connection.cursor()
    cursor.execute('SELECT uprawnienia FROM uzytkownik WHERE\
    id_uzytkownik={0}'.format(id_user))
    is_user=cursor.fetchone()[0]
    user_is_admin=bool(is_user=="admin")
    cursor.execute('END TRANSACTION;')
    cursor.close()
    return user_is_admin


@auto.doc()
def is_user_logged():
    """ Funkcja sprawdzająca, czy użytkownik jest zalogowany. Sprawdza to, czy w sesji znajduje się klucz o nazwie user_id """
    try:
        user_id=session['user_id']
        return True
    except:
        return False


@app.route('/documentation')
def documentation():
    return auto.html()


@app.route('/delete/<id>')
@auto.doc()
def delete_order(id):
    """ Route, po wejściu na który z bazy jest usuwane zamówienie o id będącym parametrem tego route'a. Nie ma żadnego layoutu strony, po poprawnym usunięciu użytkownik zostaje przekierowany do widoku zamówień użytkowników.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged():
        if is_user_admin(session['user_id']):
            try:
                cursor=connection.cursor()
                cursor.execute('delete from zamowienie where id_zamowienie={0}'.format(id))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/orders")
            except Exception as exception:
                print(exception)
                return "Coś poszło nie tak, poinformuj o tym dostawcę usługi."
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/remove/<id>')
@auto.doc()
def remove_product(id):
    """ Route, po wejściu na który z bazy jest usuwane produkt o id będącym parametrem tego route'a. Nie ma żadnego layoutu strony, po poprawnym usunięciu użytkownik zostaje przekierowany do widoku zamówień użytkowników.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged:
        if is_user_admin(session['user_id']):
            try:
                cursor=connection.cursor()
                cursor.execute("DELETE FROM produkt WHERE id_produkt={0}".format(id))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/3")
            except Exception as exception:
                print(exception)
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect(url_for('.product_info',id=id,message="remove"))
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/orders')
@auto.doc()
def orders():
    """ Route, po wejściu na który adminowi zostaje wyświetlona strona z listą zamówień wszystkich użytkowników.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged():
        if is_user_admin(session['user_id']):
            user_id=session['user_id']
            cursor = connection.cursor()
            cursor.execute('select * from zamowienia_uzytkownikow')
            cart_items_info=cursor.fetchall()
            cart=[]
            last=0
            #sortowanie cart_items_info pod względem numeru zamówienia (cart_items_info zwraca pojedyncze obiekty, w pętli poniżej są one sortowane do odpowiednich tablic)
            for items in cart_items_info:
                if items[9]!=last:
                    new_order=[]
                    new_order.append(items)
                    cart.append(new_order)
                else:
                    cart[-1].append(items)
                last=items[9]
            cursor.connection.commit()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return render_template('orders.html',items_list=cart,data=[session['fname'],session['lname']])
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/statistics')
@auto.doc()
def stats():
    """ Route, po wejściu na który administrator widzi statystyki swojej strony.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged() is True:
        if is_user_admin(session['user_id']) is True:
            cursor=connection.cursor()
            cursor.execute('select prw.id_produkt,ilosc,nazwa_rozmiaru, nazwa_produktu from produkt_rozmiar_widok prw join produkt using (id_produkt) where ilosc<10 order by prw.id_produkt')
            missing_products=cursor.fetchall() #produkty, których na magazynie jest mniej niż 10 sztuk
            cursor.execute('select * from najaktywniejsi_uzytkownicy order by sum desc limit 3')
            users=cursor.fetchall() #użytkownicy najaktywniejsi pod względem sumy pieniędzy w zamówieniach
            cursor.execute('select * from najaktywniejsi_opinie order by count desc limit 3')
            users_opinions=cursor.fetchall() #użytkownicy najaktywniejsi pod względem ilości opinii
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return render_template("statistics.html",user_is_authenticated=1,products=missing_products,users=users, users_opinions=users_opinions)
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/add_new_product', methods=['GET','POST'])
@auto.doc()
def add_new_product():
    """ Route, po wejściu na który adminowi wyświetlana jest strona z możliwością dodania nowego produktu na stronę.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged() is True:
        if is_user_admin(session['user_id']) is True:
            if request.method=="GET":
                cursor = connection.cursor()
                cursor.execute("select nazwa_kategorii,id_kategoria from kategoria")
                cats=cursor.fetchall()
                cursor.execute("select * from producent")
                producers=cursor.fetchall()
                cursor.execute("select * from gwarancja")
                warranties=cursor.fetchall()
                cursor.execute("select * from rozmiar")
                sizes=cursor.fetchall()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return render_template("add_new_product.html",cats=cats, prods=producers, warranties=warranties, sizes=sizes)
            else:
                image=Image.open(request.files["file_image"])
                cursor = connection.cursor()
                cursor.execute("select * from produkt order by id_produkt desc")
                number_of_products_pics=cursor.fetchone()[0]+1 #pobieramy najwyższe id produktów w bazie, by uniknąć konfliktów nazw przy zapisywaniu zdjęć do naszego folderu
                image.save(r"static/{0}.jpg".format(number_of_products_pics)) #do folderu static zapisujemy obraz
                photo="{0}.jpg".format(number_of_products_pics) # a jego nazwa zostanie zapisana do bazy, pozwoli to na przechowywanie prostego stringu, a nie BLOBu
                name=request.form['producer']
                cats=request.form.getlist('cats')
                prod=request.form['prod']
                warranty=request.form['warranties']
                sizes=request.form.getlist('sizes')
                price=request.form['price']
                if(cats==[] or sizes==[]): #jeśli ten if jest spełniony, to walidacja javascriptem została zmanipulowana
                    cursor.connection.commit()
                    cursor.execute('END TRANSACTION;')
                    cursor.close()
                    return "Modyfikacja javascriptu, procedura przerwana."
                else:
                    cursor.execute("INSERT INTO produkt(cena,nazwa_produktu,id_producent,id_gwarancja,zdjecie) values ({0},'{1}',{2},{3},'{4}') returning id_produkt".format(price,name,prod,warranty,photo))
                    id=cursor.fetchone()[0]
                    for i in sizes:
                        cursor.execute("INSERT INTO magazyn(id_produktu,id_rozmiar,ilosc) values({0},{1},{2})".format(id,int(i),0))
                    for i in cats:
                        cursor.execute("INSERT INTO kategoria_produkt (id_produkt, id_kategoria) VALUES ({0},{1})".format(id,int(i)))
                    cursor.connection.commit()
                    cursor.execute('END TRANSACTION;')
                    cursor.close()
                    return redirect("/{0}".format(int(cats[0])))
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/add_producer', methods=['GET','POST'])
@auto.doc()
def add_producer():
    """ Route, po wejściu na który adminowi wyświetlana jest strona z możliwością dodania nowego producenta na stronę.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged() is True:
        if is_user_admin(session['user_id']) is True:
            if request.method=="GET":
                return render_template('add_producer.html')
            else:
                cursor = connection.cursor()
                cursor.execute("INSERT INTO producent (nazwa_producenta, email) values ('{0}','{1}')".format(request.form['producer'],request.form['description']))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/3/")
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/add_courier', methods=['GET','POST'])
@auto.doc()
def add_courier():
    """ Route, po wejściu na który adminowi wyświetlana jest strona z możliwością dodania nowego kuriera na stronę.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged() is True:
        if is_user_admin(session['user_id']) is True:
            if request.method=="GET":
                return render_template("new_courier.html")
            else:
                cursor = connection.cursor()
                cursor.execute("INSERT INTO kurier (nazwa_firmy, czas_dostawy_dni, koszt_dostawy) values ('{0}',{1},{2})".format(request.form['courier'],request.form['description'],request.form['description2']))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/3/")
        else:
            return session_expired()
    return session_expired()


@app.route('/add_category', methods=['GET','POST'])
@auto.doc()
def add_cat():
    """ Route, po wejściu na który adminowi wyświetlana jest strona z możliwością dodania nowej kategorii na stronę.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged() is True:
        if is_user_admin(session['user_id']) is True:
            if request.method=="GET":
                return render_template('add_category.html')
            elif request.method=="POST":
                cursor = connection.cursor()
                cursor.execute("INSERT INTO kategoria (nazwa_kategorii, dodatkowy_opis) values ('{0}','{1}')".format(request.form['cat'],request.form['description']))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/3/")
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/categories', methods=['GET','POST'])
@auto.doc()
def cats():
    """ Route, po wejściu na który adminowi wyświetlana jest strona z możliwością usunięcia wybranej przez niego kategorii z bazy.
    Skutkuje to usunięciem wszystkich powiązań dotychczasowych produktów znajdujących się w bazie z usuwaną kategorią.
    Wymagane uprawnienia: Administrator. """
    if is_user_logged() is True:
        if is_user_admin(session['user_id']) is True:
            if request.method=="GET":
                cursor = connection.cursor()
                categories=cursor.execute("select nazwa_kategorii,kategoria.id_kategoria from kategoria")
                categories=cursor.fetchall()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return render_template("delete_category.html", categories=categories)
            elif request.method=="POST":
                cursor = connection.cursor()
                cursor.execute("DELETE FROM kategoria WHERE id_kategoria={0}".format(request.form['cat']))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/3/")
        else:
            return session_expired()
    else:
        return session_expired()


@app.route('/my_orders', methods=['GET'])
@auto.doc()
def my_orders():
    """ Route, po wejściu na który użytkownikowi wyświetlana jest strona, gdzie widzi zawartość swoich dotychczasowych niezrealizowanych zamówień.
    Wymagane uprawnienia: Zalogowany użytkownik. """
    try:
        user_id=session['user_id']
        cursor = connection.cursor()
        cursor.execute('select * from zamowienia_uzytkownikow WHERE id_uzytkownik={0}'.format(user_id))
        cart_items_info=cursor.fetchall()
        cart=[]
        last=0
        #sortowanie cart_items_info pod względem numeru zamówienia (cart_items_info zwraca pojedyncze obiekty, w pętli poniżej są one sortowane do odpowiednich tablic)
        for items in cart_items_info:
            if items[9]!=last:
                new_order=[]
                new_order.append(items)
                cart.append(new_order)
            else:
                cart[-1].append(items)
            last=items[9]
        cursor.connection.commit()
        cursor.execute('END TRANSACTION;')
        cursor.close()
        return render_template('user_orders.html',items_list=cart,data=[session['fname'],session['lname']])
    except Exception as exception:
        print(exception)
        return session_expired()


@app.route('/my_cart', methods=['GET', 'POST'])
@auto.doc()
def my_cart():
    """ Route, po wejściu na który użytkownikowi wyświetlana jest strona, gdzie widzi zawartość swojego koszyka.
    Wymagane uprawnienia: Zalogowany użytkownik. """
    try:
        message=request.args['message']
    except:
        message=""
    if request.method=="GET":
        try:
            user_id=session['user_id']
            cursor = connection.cursor()
            cursor.execute('SELECT sum(cena*ilosc),sum(ilosc) FROM koszyk join produkt using(id_produkt) join rozmiar using(id_rozmiar) join producent using(id_producent) WHERE id_uzytkownik={0}'.format(user_id))
            (sum,quantity)=cursor.fetchone()
            cursor.execute('SELECT id_produkt,id_uzytkownik,ilosc,nazwa_rozmiaru,nazwa_produktu,zdjecie,cena,nazwa_producenta,id_rozmiar FROM koszyk join produkt using(id_produkt) join rozmiar using(id_rozmiar) join producent using(id_producent) WHERE id_uzytkownik={0}'.format(user_id))
            cart_items_info=cursor.fetchall()
            cursor.execute('SELECT * FROM kurier')
            couriers=cursor.fetchall()
            cursor.execute("Select email,id_email from email_1 where id_uzytkownik={0}".format(session['user_id']))
            emails=cursor.fetchall()
            cursor.execute("Select kraj,miasto_wies,ulica,nr_budynku,nr_mieszkania,id_adres from adres where id_uzytkownik={0}".format(session['user_id']))
            adresses=cursor.fetchall()
            cursor.connection.commit()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return render_template('user_cart.html',items=cart_items_info,data=[session['fname'],session['lname']], sum=sum,couriers=couriers,quantity=quantity, emails=emails, addresses=adresses,message=message)
        except Exception as exception:
            print(exception)
            return session_expired()
    else:
        try:
            if request.form['btn']=="Zatwierdź zmiany":
                user_id=session['user_id']
                cursor = connection.cursor()
                cursor.execute('SELECT id_produkt,rozmiar.id_rozmiar FROM koszyk join produkt using(id_produkt) join rozmiar using(id_rozmiar) join producent using(id_producent) WHERE id_uzytkownik={0}'.format(user_id))
                product_list=cursor.fetchall()
                for product_id in product_list:
                    quantity=request.form['n'+str(product_id[0])+'.'+str(product_id[1])]
                    if quantity!='0':
                        try:
                            cursor.execute('UPDATE koszyk SET ilosc={0} WHERE id_produkt={1} AND id_rozmiar={2}'.format(quantity,product_id[0],product_id[1]))
                            cursor.connection.commit()
                        except Exception:
                            cursor.execute('END TRANSACTION;')
                            cursor.close()
                            return redirect(url_for('.my_cart', message="quantity"))
                    else:
                        cursor.execute('DELETE FROM koszyk WHERE id_produkt={0} AND id_rozmiar={1}'.format(product_id[0],product_id[1]))
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/my_cart")
            elif request.form['btn']=="Wyślij zamówienie":
                email=request.form['email']
                adr=request.form['address']
                user=session['user_id']
                courier=request.form['courier']
                if adr=="None":
                    return redirect(url_for('.new_address', message="adres"))
                cursor = connection.cursor()
                cursor.execute("SELECT koszt_dostawy FROM kurier WHERE id_kurier={0}".format(courier))
                courier_payment=cursor.fetchone()[0]
                cursor.execute('SELECT sum(cena*ilosc) FROM koszyk join produkt using(id_produkt) join rozmiar using(id_rozmiar) join producent using(id_producent) WHERE id_uzytkownik={0}'.format(user))
                sum=cursor.fetchone()[0]
                flag=0
                cursor.execute("SELECT * FROM koszyk WHERE id_uzytkownik={0}".format(user))
                cart=cursor.fetchall()
                for cart_product in cart:
                    cursor.execute("SELECT ilosc FROM magazyn WHERE id_produktu={0} AND id_rozmiar={1}".format(cart_product[1],cart_product[2]))
                    available_products_quantity=cursor.fetchone()[0]
                    if available_products_quantity>=cart_product[3]:
                        pass
                    else:
                        flag=1
                        cursor.execute('END TRANSACTION;')
                        cursor.close()
                        return redirect(url_for('.my_cart', message="too few"))
                if flag==0:
                    cursor.execute("INSERT INTO zamowienie (id_kurier,id_uzytkownik,id_adres,id_email, data_zlozenia, kwota_do_zaplaty) values({0},{1},{2},{3},'{4}',{5}) returning id_zamowienie".format(courier,user,adr,email,datetime.date.today(),sum+courier_payment))
                last_order_id=cursor.fetchone()[0]

                if flag==0:
                    for cart_product in cart:
                        cursor.execute("INSERT INTO zamowienie_towar (id_zamowienie,id_produkt,id_rozmiar,ilosc) VALUES ({0},{1},{2},{3})".format(last_order_id,cart_product[1],cart_product[2],cart_product[3]))
                    cursor.execute("DELETE FROM koszyk WHERE id_uzytkownik={0}".format(user))
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/my_orders")
            else:
                return "Proszę nie próbować oszukać systemu, to tylko biedny projekt studencki"
        except Exception as exception:
            print(exception)
            return session_expired()


@app.route('/product/<id>', methods=['GET', 'POST'])
@auto.doc()
def product_info(id):
    """ Route, po wejściu na który użytkownikowi wyświetlana jest strona, gdzie widzi szczegóły produktu charakteryzującego się id będącego parametrem route'a.
    W zależności od uprawnień, możliwości użytkownika na tej stronie są odpowiednio dostosowywane.
    Wymagane uprawnienia: Zalogowany użytkownik/Administrator/Użytkownik niezalogowany """
    check_if_logged=""
    try:
        message=request.args['message']
    except:
        message=""
    sizes=[]
    if request.method=="GET":
        try: # if user is logged
            check_if_logged=session['username1']
            try:
                cursor = connection.cursor()
                cursor.execute("Select * from gwarancja join produkt using (id_gwarancja) where id_produkt={0}".format(id))
                result=cursor.fetchone()
                cursor.execute("select * from produkt_info_widok where id_produkt={0}".format(id))
                result2 = cursor.fetchone()
                result3=[session['fname'],session['lname']]
                cursor.execute("select nazwa_rozmiaru,ilosc,id_rozmiar from produkt_rozmiar_widok where id_produkt={0}".format(id))
                sizes=cursor.fetchall()
                cursor.execute("select tresc_opinii,imie,nazwisko,ilosc_gwiazdek,data,id_uzytkownik from uzytkownik_opinie_widok where id_produkt={0}".format(id))
                opinions=cursor.fetchall()
                number_of_products=0
                for size in sizes:
                    number_of_products+=size[1]
                my_rating=0
                for record in opinions:
                    if record[5]==session['user_id']:
                        my_rating=record[3]
                average_rating=0
                for record in opinions:
                    average_rating+=record[3]
                if opinions:
                    average_rating/=len(opinions)
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return render_template("product_info.html",warranty=result[1:3], info=result2,data=result3,user_is_admin=is_user_admin(session['user_id']), user_is_authenticated=1,stars=average_rating,opinions=opinions, message=message,my_rating=my_rating,sizes=sizes, number_of_products=number_of_products,id=id)
            except Exception as exception:
                print(exception)
                return "Blad polaczenia z baza"
        except: #if user is not logged
            cursor = connection.cursor()
            cursor.execute("Select * from gwarancja join produkt using (id_gwarancja) where id_produkt={0}".format(id))
            result=cursor.fetchone()
            cursor.execute("select * from produkt_info_widok where id_produkt={0}".format(id))
            result2 = cursor.fetchone()
            cursor.execute("select nazwa_rozmiaru,ilosc,id_rozmiar from produkt_rozmiar_widok where id_produkt={0}".format(id))
            sizes=cursor.fetchall()
            number_of_products=0
            for size in sizes:
                number_of_products+=size[1]
            cursor.execute("select tresc_opinii,imie,nazwisko,ilosc_gwiazdek,data from uzytkownik_opinie_widok where id_produkt={0}".format(id))
            opinions=cursor.fetchall()
            average_rating=0
            for record in opinions:
                average_rating+=record[3]
            if opinions:
                average_rating/=len(opinions)
            cursor.connection.commit()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return render_template("product_info.html",warranty=result[1:3], info=result2, user_is_authenticated=0,opinions=opinions,message=message,stars=average_rating,sizes=sizes,number_of_products=number_of_products)
    elif request.method=="POST":
        try:
            check_if_logged=session['username1']
            if request.form['btn']=="Prześlij opinię":
                try:
                    cursor = connection.cursor()
                    cursor.execute("SELECT * FROM opinie WHERE id_produkt={0} AND id_uzytkownik={1}".format(id,session['user_id']))
                    result=cursor.fetchone()
                    if result:
                        cursor.execute("UPDATE opinie SET ilosc_gwiazdek={2}, tresc_opinii='{3}',data='{4}' where id_produkt={0} and id_uzytkownik={1}".format(id,session['user_id'],request.form['rating'],request.form['addComment'],datetime.datetime.now().strftime('%Y-%m-%d')) )
                        cursor.connection.commit()
                        cursor.execute('END TRANSACTION;')
                        cursor.close()
                        message="OPUPD"
                        return redirect(url_for('.product_info',id=id, message=message))
                    else:
                        cursor.execute("INSERT INTO opinie(id_produkt,id_uzytkownik,ilosc_gwiazdek,tresc_opinii,data) values('{0}','{1}',{2},'{3}','{4}')".format(id,session['user_id'],request.form['rating'],request.form['addComment'],datetime.datetime.now().strftime('%Y-%m-%d')) )
                        cursor.connection.commit()
                        cursor.execute('END TRANSACTION;')
                        cursor.close()
                        message="OPSET"
                        return redirect(url_for('.product_info',id=id, message=message))
                except Exception as exception:
                    print(exception)
                    return "Blad polaczenia z baza"
            elif request.form['btn']=="Dodaj do koszyka":
                cursor = connection.cursor()
                cursor.execute('SELECT ilosc FROM magazyn WHERE id_produktu={0} and id_rozmiar={1}'.format(id,request.form['sizes']))
                info_product_quantity=cursor.fetchone()
                if info_product_quantity[0]>0:
                    cursor.execute('SELECT ilosc FROM koszyk WHERE id_produkt={0} and id_rozmiar={2} and id_uzytkownik={1}'.format(id,session['user_id'],request.form['sizes']))
                    record=cursor.fetchone()
                    if record is None:
                        try:
                            cursor.execute('INSERT INTO KOSZYK(id_uzytkownik,id_produkt,id_rozmiar,ilosc) values ({0},{1},{2},1)'.format(session['user_id'],id,request.form['sizes']))
                            cursor.connection.commit()
                            cursor.execute('END TRANSACTION;')
                            cursor.close()
                            message="CSET"
                            return redirect(url_for('.product_info',id=id, message=message))
                        except:
                            cursor.connection.commit()
                            cursor.execute('END TRANSACTION;')
                            cursor.close()
                            message="Za mało produktów w magazynie by spełnić to żądanie."
                            return redirect(url_for('.product_info',id=id, message=message))
                    else:
                        try:
                            cursor.execute('UPDATE KOSZYK SET ilosc={0} WHERE id_produkt={1} and id_rozmiar={2} and id_uzytkownik={3}'.format(record[0]+1,id,request.form['sizes'],session['user_id']))
                            cursor.connection.commit()
                            cursor.execute('END TRANSACTION;')
                            cursor.close()
                            message="CSET"
                            return redirect(url_for('.product_info',id=id, message=message))
                        except:
                            cursor.connection.commit()
                            cursor.execute('END TRANSACTION;')
                            cursor.close()
                            message="Za mało produktów w magazynie by spełnić to żądanie."
                            return redirect(url_for('.product_info',id=id, message=message))
                else:
                    cursor.connection.commit()
                    cursor.execute('END TRANSACTION;')
                    cursor.close()
                    message="P0"
                    return redirect(url_for('.product_info',id=id, message=message))
            elif request.form['btn'][0:18]=="Usuń ten komentarz":
                if is_user_logged():
                    if is_user_admin(session['user_id']):
                        x=request.form['btn']
                        user_info=x[19:]
                        user_id_to_delete=user_info[7:-1]
                        cursor = connection.cursor()
                        cursor.execute("DELETE FROM opinie WHERE id_uzytkownik={0} AND id_produkt={1}".format(user_id_to_delete,id))
                        cursor.connection.commit()
                        cursor.execute('END TRANSACTION;')
                        cursor.close()
                        return redirect("/product/{0}".format(id))
                    else:
                        return session_expired()
                else:
                    return session_expired()
            elif request.form['btn']=="Dodaj do magazynu":
                if is_user_logged():
                    if is_user_admin(session['user_id']):
                        cursor=connection.cursor()
                        cursor.execute("select * from magazyn where id_produktu={0}".format(id))
                        prods=cursor.fetchall()
                        for i in prods:
                            quantity=request.form['quantity{0}'.format(i[1])]
                            id_size=i[2]
                            id_object=i[0]
                            try:
                                if quantity:
                                    cursor.execute("update magazyn set ilosc=ilosc+{2} where id_produktu={0} and id_rozmiar={1};".format(id_object,i[1],quantity))
                            except Exception as e:
                                cursor.connection.commit()
                                cursor.execute('END TRANSACTION;')
                                cursor.close()
                                return redirect(url_for('.product_info',id=id, message="quantity"))
                        cursor.connection.commit()
                        cursor.execute('END TRANSACTION;')
                        cursor.close()
                        return redirect("/product/{0}".format(id))
            else:
                return "Proszę nie próbować oszukać systemu, to tylko biedny projekt studencki"
        except Exception as exception:
            print(exception)
            return session_expired()


@app.route('/login',methods=['GET','POST'])
@auto.doc()
def login():
    """ Route, po wejściu na który użytkownikowi wyświetlana jest strona, gdzie ma możliwość zalogowania się do serwisu.
    Po poprawnym zalogowaniu nawiązywana jest sesja. Hasło zapisywane w bazie jest odpowiednio hashowane.
    Wymagane uprawnienia: Użytkownik niezalogowany. """
    if request.method=='POST':
        cursor = connection.cursor()
        email=request.form['email']
        email=email.lower()
        password=request.form['pass']
        user=cursor.execute("select haslo,ziarno_hasla,imie,nazwisko,id_uzytkownik from uzytkownik_emaile_widok where lower(email)='{0}'".format(email))
        user=cursor.fetchone()
        cursor.execute('END TRANSACTION;')
        cursor.close()
        if user:
            password=generate_heshlib_key(password,user[1])
            password=bytes(password)
            if str(psycopg2.Binary(password))==str(psycopg2.Binary(user[0])):
                session[email]=True
                session.permanent=True
                session['user_id']=int(user[4])
                session['is_admin']=is_user_admin(user[4])
                session['username1']=email
                session['fname']=user[2]
                session['lname']=user[3]
                return redirect("/3")
            else:
                return render_template("login.html",status=0)
        else:
            return render_template("login.html",status=0)

    else:
        if is_user_logged():
            return redirect("/3")
        else:
            return render_template("login.html")


@app.route('/logout',methods=['GET','POST'])
@auto.doc()
def logout():
    """ Route, po wejściu na który użytkownik będący zalogowany jest wylogowywany (jego sesja niszczona) i przekierowywany na stronę główną.
    Wymagane uprawnienia: Użytkownik zalogowany, Administrator"""
    if session.get('username1'):
        session['username1']=False
        session.pop('username1')
        session.pop('user_id')
        session.pop('is_admin')
        session.pop('fname')
        session.pop('lname')
    return redirect("/3")


def session_expired():
    """ Funkcja wywoływana gdy użytkownik wchodzi na stronę, do której nie ma uprawnień, jego sesja wygasła lub ze strony aplikacji pojawi się niespodziewany błąd."""
    if is_user_logged():
        if is_user_admin(session['user_id']):
            return render_template('logged_out.html',user_is_authenticated=1,user_is_admin=1,dane=[session['fname'],session['lname']])
        else:
            return render_template('logged_out.html',user_is_authenticated=1,dane=[session['fname'],session['lname']])
    else:
        return render_template('logged_out.html')


@app.route('/register',methods=['GET','POST'])
@auto.doc()
def register():
    """ Route, po wejściu na który użytkownik niezalogowany widzi stronę, na której może się zarejestrować do aplikacji.
    Wymagane uprawnienia: Użytkownik niezalogowany"""
    if request.method=='POST':
        fname=request.form['fname']
        email=request.form['email']
        email=email.lower()
        lname=request.form['lname']
        password=request.form['pass']
        password=generate_heshlib_key(password,salt)
        password=bytes(password)
        try:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO uzytkownik (Imie,Nazwisko,Haslo,Uprawnienia,Ziarno_hasla) values ('"+fname+"','"+lname+"',{0},'user',{1}) returning id_uzytkownik".format(psycopg2.Binary(password),psycopg2.Binary(salt)))
            result=cursor.fetchone()
            cursor.execute("INSERT INTO email_1(czy_domyslny,id_uzytkownik,email) values(true,{0},lower('{1}'))".format(result[0],email))
            cursor.connection.commit()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return render_template("login.html")
        except Exception as exception:
            print(exception)
            cursor.connection.rollback()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return "Nie udalo się, ten email istnieje w bazie lub email nie spełnia kryteriów emaila. <a href='/register'> Spróbuj ponownie </a>"
    elif request.method=='GET':
        try:
            check_if_logged=session['username1']
            return redirect("/3")
        except KeyError as error:
            return render_template("register.html")
    else:
        return "Niespodziewany błąd."


@app.route('/data',methods=['GET','POST'])
@auto.doc()
def data():
    """ Route, po wejściu na który użytkownikownik będący zalogowany może zobaczyć stronę, gdzie prezentowane mu są jego dane osobowe i możliwość ich modyfikacji.
    Wymagane uprawnienia: Użytkownik zalogowany, Administrator"""
    if request.method=="GET":
        try:
            username=session['username1']
        except:
            return session_expired()
        if username!="":
            try:
                cursor = connection.cursor()
                cursor.execute("Select imie,nazwisko,id_uzytkownik,email from uzytkownik_emaile_widok where id_uzytkownik={0} order by czy_domyslny DESC".format(session['user_id']))
                result=cursor.fetchall()
                cursor.execute("Select kraj,miasto_wies,nr_mieszkania,ulica,nr_budynku from adres where id_uzytkownik={0}".format(session['user_id']))
                adresses=cursor.fetchall()
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return render_template('user_data.html',user=result[0][3],dane=result,address=adresses, user_is_authenticated=1,user_is_admin=is_user_admin(session['user_id']))
            except:
                return "Oops, cos poszlo nie tak"
        else:
            return redirect("/data")
    elif request.method=="POST":
        if session['username1']:
            try:
                fname=request.form['firstName']
                lname=request.form['lastName']
                email=request.form['email']
                cursor = connection.cursor()
                cursor.execute("Update email_1 set czy_domyslny=false where id_uzytkownik={0}".format(session['user_id']))
                cursor.execute("Update email_1 set czy_domyslny=true where email='{0}'".format(email))
                cursor.execute("Update uzytkownik set imie='{0}', nazwisko='{1}' where id_uzytkownik={2}".format(fname,lname,session['user_id']))
                session['fname']=fname
                session['lname']=lname
                cursor.connection.commit()
                cursor.execute('END TRANSACTION;')
                cursor.close()
                return redirect("/3")
            except Exception as exception:
                print(exception)
                return "Oops, cos poszlo nie tak2"
        else:
            return redirect("/data")
    else:
        return "Niespodziewany błąd."


@app.route('/',methods=['GET','POST'])
@app.route('/<int:id>/',methods=['GET','POST'])
@auto.doc()
def index_logged(id=4):
    """ Route, po wejściu na który użytkownikownik widzi produkty znajdujące się w kategorii opisanej id będącym parametrem route'a (domyślnie 4 - męskie).
    Wymagane uprawnienia: Użytkownik zalogowany, Administrator, Użytkownik niezalogowany"""
    check_if_logged=""
    if is_user_logged():
        check_if_logged=session['username1']
    else:
        cursor = connection.cursor()
        result = cursor.execute("select * from produkt_info_widok where id_kategoria={0}".format(id))
        result=cursor.fetchall()
        categories=cursor.execute("select nazwa_kategorii,kategoria.id_kategoria,count(p.id_produkt) from kategoria left join kategoria_produkt kp on kategoria.id_kategoria = kp.id_kategoria left join produkt p on kp.id_produkt = p.id_produkt group by kategoria.id_kategoria,kategoria.nazwa_kategorii order by id_kategoria;")
        categories=cursor.fetchall()
        cursor.execute('END TRANSACTION;')
        cursor.close()
        return render_template("gallery.html",contents=result,categories=categories,user_is_authenticated=0)

    if check_if_logged:
        user_data={
            "email": session['username1'],
            "imie": session['fname'],
            "nazwisko": session['lname']
            }
        cursor = connection.cursor()
        result = cursor.execute("select * from produkt_info_widok where id_kategoria={0}".format(id))
        result=cursor.fetchall()
        categories=cursor.execute("select nazwa_kategorii,kategoria.id_kategoria,count(p.id_produkt) from kategoria left join kategoria_produkt kp on kategoria.id_kategoria = kp.id_kategoria left join produkt p on kp.id_produkt = p.id_produkt group by kategoria.id_kategoria,kategoria.nazwa_kategorii order by id_kategoria;")
        categories=cursor.fetchall()
        cursor.execute('END TRANSACTION;')
        cursor.close()
        return render_template('gallery.html',contents=result,categories=categories,user_is_authenticated=1,user_is_admin=session['is_admin'],data=user_data)
    else:
        return redirect("/3")


@app.route('/new_email',methods=['GET','POST'])
@auto.doc()
def new_email():
    """ Route, po wejściu na który użytkownikownik widzi stronę z formularzem umożliwiającym dodanie nowego emaila.
    Wymagane uprawnienia: Użytkownik zalogowany, Administrator"""
    if request.method=="GET":
        if is_user_logged():
            return render_template("new_email.html")
        return session_expired()
    elif request.method=='POST':
        email=request.form['email']
        print(email)
        try:
            cursor = connection.cursor()
            cursor.execute("Insert into email_1 (czy_domyslny,id_uzytkownik,email) values (false,{0},lower('{1}'))".format(session['user_id'],email))
            cursor.connection.commit()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return redirect("/data")
        except Exception as exception:
            print(exception)
            cursor.connection.rollback()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return "Podany email nie spelnia wymogów emaila lub istnieje już w naszej bazie. <a href='/new_email'> POWRÓT </a> "
    else:
        return "Niespodziewany błąd."


@app.route('/new_address',methods=['GET','POST'])
@auto.doc()
def new_address():
    """ Route, po wejściu na który użytkownikownik widzi stronę z formularzem umożliwiającym dodanie nowego adresu.
    Wymagane uprawnienia: Użytkownik zalogowany, Administrator"""
    try:
        message=request.args['message']
    except:
        message=""
    if request.method=="GET":
        if is_user_logged():
            return render_template("new_address.html",message=message)
        else:
            return session_expired()

    elif request.method=='POST':
        country=request.form['inputCountry']
        city=request.form['inputCity']
        building=request.form['inputBuilding']
        street=request.form['inputStreet']
        flat=request.form['inputFlat']
        try:
            cursor = connection.cursor()
            if street and flat:
                executable_statement="Insert into adres (id_uzytkownik,kraj,miasto_wies,nr_mieszkania,nr_budynku,ulica) values ({0},'{1}','{2}',{3},'{4}','{5}')".format(session['user_id'],country,city,flat,building,street)
            elif flat and not street:
                executable_statement="Insert into adres (id_uzytkownik,kraj,miasto_wies,nr_mieszkania,nr_budynku) values ({0},'{1}','{2}',{3},'{4}')".format(session['user_id'],country,city,flat,building)
            elif street and not flat:
                executable_statement="Insert into adres (id_uzytkownik,kraj,miasto_wies,nr_budynku,ulica) values ({0},'{1}','{2}','{3}','{4}')".format(session['user_id'],country,city,building,street)
            else:
                executable_statement="Insert into adres (id_uzytkownik,kraj,miasto_wies,nr_budynku) values ({0},'{1}','{2}','{3}')".format(session['user_id'],country,city,building)
            cursor.execute(executable_statement)
            cursor.connection.commit()
            cursor.execute('END TRANSACTION;')
            cursor.close()
            return redirect("/data")
        except Exception as exception:
            print(exception)
            return "Oops, cos poszlo nie tak"
    else:
        return "Niespodziewany błąd."

if __name__=="__main__":
    app.run(debug=True)

#if __name__=="__main__":
#    app.run(host='0.0.0.0', port=port)
