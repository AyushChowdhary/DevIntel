def evaluate_response(query, answer, context):
    score = 0

    if query.lower() in answer.lower():
        score += 1

    if len(answer) > 50:
        score += 1

    if "file" in answer.lower():
        score += 1

    return score / 3

