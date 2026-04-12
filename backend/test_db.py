from flask_mysqldb import MySQL
from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)

@app.route('/test')
def test_db():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT 1')
        return 'Database Connected Successfully!'
    except Exception as e:
        return f'Error: {str(e)}'

if __name__ == '__main__':
    app.run(debug=True)