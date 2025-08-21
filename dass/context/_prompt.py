##################################################
#               extract prompt                   # 
##################################################

START_EXTRACTION_TAG = "<START_EXTRACTION>"
NO_RELATED_EXTRACTION_TAG = "<NO_RELATED>"

""" extract prompt related to user query from history messages
If there are something related to user query then output string started with START_EXTRACTION_TAG
else then ouptut started with NO_RELATED_EXTRACTION_TAG.

Args:
    START_EXTRACTION_TAG: start extraction tag for parsing easily
    NO_RELATED_EXTRACTION_TAG: no related tag
    user_query: user query
    history_messages: history messages.
"""

extract_prompt = """You are a helpful assistant for extracting relative paragraphs, sentences, topics and messages in a long text or lots of paragraphs.
You should carefully consider whether your extractions are the most relative to the `<user_query>`. I trust you can do it well.
Notice that sometimes the words, sentences and paragraphs are ambiguous. When you encount the situation you can:
    1. analyze them more deeply
    2. extract them both but post your considerations
    3. pass them directly.
Output format should be started with {START_EXTRACTION_TAG}. For example:
```
{START_EXTRACTION_TAG}:
....
```
If you think content in `<history_messages>` are all not relative you should output started with {NO_RELATED_EXTRACTION_TAG} and claim your reasons for me. For example:
```
{NO_RELATED_EXTRACTION_TAG}:
I think all history messages are not relative to user query because ...
```

<user_query>
{user_query}
</user_query>

<history_messages>
{history_messages}
</history_messages>
"""