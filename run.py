from dotenv import load_dotenv
load_dotenv()  # 必须在导入app之前加载环境变量

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
