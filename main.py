from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
class Input_Data(BaseModel):
    value: int

def generate_fibonacci(value: int):
    if value <= 0:
        return []
    elif value == 1:
        return [0]
    elif value == 2:
        return [0, 1]
    
    fibon_series = [0, 1]
    for i in range(2, value):
        next_number = fibon_series[-1] + fibon_series[-2]
        fibon_series.append(next_number)
    
    return fibon_series

@app.post("/fibonacci")
def fibonacci_series(data: Input_Data):
    result = generate_fibonacci(data.value)
    return {"method": "POST", "input": data.value, "fibonacci_series": result}

@app.get("/fibonacci")
def fibonacci_series_get(value: int):
    result = generate_fibonacci(value)
    return {"method": "GET", "input": value, "fibonacci_series": result}