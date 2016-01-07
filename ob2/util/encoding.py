def wrangle_to_unicode(text):
    """
    Converts some object to unicode text. Use the same decoding heuristic that's most commonly used
    in other places.

    """
    try:
        text = str(text).decode("utf-8")
    except UnicodeDecodeError:
        text = str(text).decode("latin-1")
    return text
