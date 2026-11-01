from pathlib import Path
import sys

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab9_core.conversation import DocumentChat


def test_followup_failure_keeps_history_and_clear_works():
    class Model:
        replies = ['Tuning is manual. [1]','ADS optimization',RuntimeError('injected failure')]
        def invoke(self, messages):
            reply = self.replies.pop(0)
            if isinstance(reply,Exception):raise reply
            return AIMessage(content=reply)
    class Vectors:
        queries = []
        def similarity_search_with_score(self, query, k):
            self.queries.append(query)
            return [(Document(page_content='Tuning is manual.',metadata={'source':'ADS.pdf','page':5}),0.9)]
    vectors = Vectors()
    chat = DocumentChat(Model(),vectors)
    chat.ask('What is tuning?')
    assert len(chat.history)==2
    with pytest.raises(RuntimeError):chat.ask('How does it compare?')
    assert len(chat.history)==2 and vectors.queries[-1]=='ADS optimization'
    chat.clear()
    assert chat.history==[]
