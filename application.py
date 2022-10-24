import os
import requests
from dotenv import load_dotenv
from flask import Flask, session, render_template, request, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

load_dotenv('variables_entorno.env')
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# if not os.environ.get("API_KEY"):
   # raise RuntimeError("API_KEY not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/", methods=["GET", "POST"])

    # Si el usuario no ha ingresado, no prodrá ingresar a la función index
    # y en vez, siendo ejecutada la función decorada y retornada si ya hay una sesión

@login_required
def index():
    if request.method == "POST":
        info = request.form.get("libro_info")
        if not info:
            libros = db.execute("SELECT * FROM registro_libros").fetchall()
        else:
            libros = db.execute("SELECT * FROM registro_libros WHERE isbn ILIKE '%"+info+"%' or title ILIKE '%"+info+"%' or author ILIKE '%"+info+"%'").fetchall()
            if len(libros) < 1:
                return apology("No hay coincidencias")

        return render_template("index.html", libros=libros)  

    else:
        libros = db.execute("SELECT * FROM registro_libros").fetchall()
        return render_template("index.html", libros=libros)
            
@app.route("/<isbn>", methods=["GET", "POST"])
def libro(isbn):
    if request.method == "GET":

        respuesta = requests.get("https://www.googleapis.com/books/v1/volumes?q=isbn:"+isbn+"&key=AIzaSyBEeffGO8NHrwaBuBx8VLmnBwhG82Pa0SM")
        respuesta = respuesta.json()
        try:
            puntaje_promedio = respuesta['items'][0]['volumeInfo']['averageRating']
            cantidad_valoraciones = respuesta['items'][0]['volumeInfo']['ratingsCount']
        except:
            puntaje_promedio = 0
            cantidad_valoraciones = 0
        libro_descripcion = respuesta['items'][0]['volumeInfo']['description']
        libro_datos = db.execute("SELECT * FROM registro_libros WHERE isbn = :isbn", {"isbn":isbn}).fetchall()
        libro_id = libro_datos[0][0]
        reseñas = db.execute("SELECT usuarios.usuario, reseña, puntaje FROM reseñas INNER JOIN usuarios ON usuarios.id = reseñas.usuario_id WHERE libros_id = :libro_id", {"libro_id": libro_id}).fetchall()
        return render_template("libro.html", libro_datos = libro_datos, puntaje_promedio = puntaje_promedio, cantidad_valoraciones = cantidad_valoraciones, reseñas = reseñas, libro_descripcion = libro_descripcion)
    else:
        usuario_id = session["user_id"]
        reseña = request.form.get("reseña_usuario")
        puntaje = request.form.get("valoracion")

        libro_datos = db.execute("SELECT * FROM registro_libros WHERE isbn = :isbn", {"isbn":isbn}).fetchall()
        libro_id = libro_datos[0][0]
        
        verificar_reseña=db.execute("SELECT * FROM reseñas WHERE usuario_id=:usuario_id AND libros_id=:libro_id", {"usuario_id":usuario_id, "libro_id":libro_id}).fetchall()
        print(len(verificar_reseña))
        if len(verificar_reseña) == 1: 
            return apology("Solo puede realizar una reseña")
    
        db.execute("INSERT INTO reseñas (reseña, puntaje, usuario_id, libros_id) VALUES (:reseña, :puntaje, :usuario_id, :libro_id)",{"reseña": reseña, "puntaje": int(puntaje), "usuario_id": usuario_id, "libro_id": libro_id})
        db.commit()

        return redirect("/"+isbn)


@app.route("/api/<isbn>")
def api(isbn):

    datos = db.execute("SELECT title, author, year, isbn, COUNT(reseñas.id) as review_count, AVG(reseñas.puntaje) as average_score FROM registro_libros INNER JOIN reseñas ON registro_libros.id = reseñas.libros_id WHERE isbn = :isbn GROUP BY title, author, year, isbn",{"isbn": isbn}).fetchall()
    datos = dict(datos[0])
    datos['average_score']= "{:.2f}".format(float(datos['average_score']))
    print(datos)
    return jsonify(datos)
 


@app.route("/login", methods=["GET", "POST"])
def login():

    """Limpiamos los datos de la sesión"""
    session.clear()

    # Cuando el usuario manda el formulario
    if request.method == "POST":
        # Guardar lo que rellenó el usuario en el campo de usuario del formulario
        session["user_id"] = request.form.get("usuario")
        
        if not request.form.get("usuario"):
            return apology("Debe proveer un usuario", 403)

        elif not request.form.get("contraseña"):
            return apology("Debe proveer una contraseña", 403)
        
        # Buscar en base de datos por el usuario
        rows = db.execute("SELECT * FROM usuarios WHERE usuario = :usuario", {"usuario":request.form.get("usuario")}).fetchall()

        # Comprobar si existe el usuario ingresado y la contraseña coincide
        if len(rows) != 1 or not check_password_hash(rows[0][1], request.form.get("contraseña")):
            return apology("invalid username and/or password", 403)

         # Recordar que usuario ingresó   
        session["user_id"] = rows[0][0]   

        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        contraseña = request.form.get("contraseña")
        confirmacion = request.form.get("contraseña2")

        if not usuario:
            return apology("Debe escribir un usuario")
        if not contraseña:
            return apology("Debe escribir una contraseña")
        if not confirmacion:
            return apology("Condfirmación de contraseña no realizada")

        if contraseña != confirmacion:
            return apology("Las contraseñas no coinciden")
        
        hash2 = generate_password_hash(contraseña)

        try:
            db.execute("INSERT INTO usuarios (usuario, user_password) VALUES (:usuario, :contraseña)", {"usuario":usuario, "contraseña":hash2})
            db.commit()
        except:
            return apology("El usuario ya existe")

        user_id = db.execute("SELECT id FROM usuarios WHERE usuario = :usuario", {"usuario":request.form.get("usuario")}).fetchall()
        session["user_id"] = user_id
        return redirect("/login")

    else:
        return render_template("registro.html")

@app.route("/logout")
def logout():

    # Olvidar que usuario estaba en la sesión
    session.clear()

    # Redireccionar para ingresar nuevamente
    return redirect("/")



