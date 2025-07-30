
from clarifai.client.model import Model

image_url = "https://s3.amazonaws.com/samples.clarifai.com/featured-models/image-captioning-statue-of-liberty.jpeg"

model_url = "https://clarifai.com/clarifai/main/models/food-item-recognition"
model_prediction = Model(url=model_url, pat="c4b6fbbfd9384b92a35be2a0de5e97ab").predict_by_url(image_url)

print(model_prediction.outputs[0].data.text.raw)
