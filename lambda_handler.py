from mangum import Mangum
from src.main import app

# FastAPI를 Lambda 핸들러로 변환
handler = Mangum(app, lifespan="off")