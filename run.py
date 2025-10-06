from app import create_app

# Cria a aplicação usando a nossa fábrica
app = create_app()

# Permite executar o servidor com 'python run.py'
if __name__ == '__main__':
    app.run(debug=True)