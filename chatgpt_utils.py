import os
import openai

def get_fact_for_distance(distance, incoming_model, openai_secret_key):
    openai.api_key = openai_secret_key

    prompt = f"I need two points in the world that are apprximately {distance} meters apart.  It does not have to be cities.  The more obscure the points, the better, but the distance apart must be close to exact.In your response convert meters to miles and start your response with that conversion, like this as an example (2200 meters = 1.367miles). Then give me an interesting fact about both points."

    if incoming_model == "gpt-3.5-turbo":
        messages=[
            {"role": "system", "content":"You are a helpful assistant specializing in geography and trivia."},
            {"role": "user", "content": prompt},
        ]

        response = openai.ChatCompletion.create(
        model=incoming_model,
        messages=messages,
        temperature=1,
        max_tokens=1000
        )
        fact = response.choices[0].message['content'].strip()

    elif incoming_model == "text-davinci-003":
        response = openai.Completion.create(engine=incoming_model, prompt=prompt, max_tokens=1000)
        fact = response.choices[0].text.strip()

    else:
        fact = "Model not recognized.  Contact your local rad developer at will, or me."

    return fact