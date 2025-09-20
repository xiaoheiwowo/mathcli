import os
import json


def load_questions():
    file_name = os.path.join(os.path.dirname(__file__), 'questions.json')
    with open(file_name, 'r') as f:
        return json.load(f)


questions = load_questions()