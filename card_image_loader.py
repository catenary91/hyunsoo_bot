import os
from io import BytesIO

import discord
from PIL import Image

CARD_IMAGE_DIR = os.path.join('card', 'medium_small')
CARD_WIDTH = 172
CARD_HEIGHT = 264

SHAPES = ['S', 'D', 'H', 'C']
NUMBERS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'A', 'J', 'Q', 'K', 'A']

class Card:
    def __init__(self, card_str):
        self.shape = card_str[0]
        self.shape_index = SHAPES.index(self.shape)
        self.number = card_str[1:]
        self.number_index = NUMBERS.index(self.number)
    
    def __eq__(self, other):
        return self.shape == other.shape and self.number == other.number

    def __str__(self):
        return self.shape+self.number

    def filename(self):
        return os.path.join(CARD_IMAGE_DIR, f'{self.shape}{self.number}.png')

def make_card(shape, number):
    return Card(SHAPES[shape]+NUMBERS[number])
    

# Image -> discord.File
def image_to_file(image, filename='card.png'):
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    buffer.seek(0)
    return discord.File(buffer, filename=filename)

# Card -> Image
def card_to_image(card):
    return Image.open(card.filename()).convert("RGBA")

# [Image] -> Image
def concat_card_image(image_list): 
    if len(image_list) == 1:
        return image_list[0]
    
    n = len(image_list)
    result = Image.new("RGBA", (CARD_WIDTH*n, CARD_HEIGHT), (255, 255, 255, 0))
    for i, image in enumerate(image_list):
        result.paste(image, (i*CARD_WIDTH, 0, (i+1)*CARD_WIDTH, CARD_HEIGHT))

    return result

# [Card] -> discord.File
def card_list_to_file(card_list):
    image_list = [card_to_image(card) for card in card_list]
    result_image = concat_card_image(image_list)
    return image_to_file(result_image)