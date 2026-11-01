"""Conversation over a document library using the standalone CLI prompts."""
from pathlib import Path
import sys

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'embedding'))
from chat_cli import ANSWER_SYSTEM, REWRITE_SYSTEM, MAX_HISTORY_TURNS, format_context


class DocumentChat:
    def __init__(self, model, vectors, k=6):
        if k<1:
            raise ValueError('k must be positive')
        self.model, self.vectors, self.k = model, vectors, k
        self.history = []
        self.rewrite = ChatPromptTemplate.from_messages([
            ('system',REWRITE_SYSTEM),MessagesPlaceholder('history'),('human','{question}')])
        self.answer = ChatPromptTemplate.from_messages([
            ('system',ANSWER_SYSTEM),MessagesPlaceholder('history'),('human','{question}')])

    def _request(self, prompt, **values):
        response = self.model.invoke(prompt.format_messages(history=self.history,**values))
        content = StrOutputParser().invoke(response).strip()
        if not content:
            raise ValueError('The model returned no text')
        return content

    def clear(self):
        self.history.clear()

    def ask(self, question):
        question = question.strip()
        if not question:
            raise ValueError('Question must not be empty')
        query = self._request(self.rewrite,question=question) if self.history else question
        matches = self.vectors.similarity_search_with_score(query,k=self.k)
        if not matches:
            raise ValueError('The document index is empty')
        passages = [dict(filename=d.metadata['source'],page=d.metadata['page'],
                         text=d.page_content,score=score) for d,score in matches]
        answer = self._request(self.answer,question=question,context=format_context(passages))
        self.history = (self.history+[HumanMessage(content=question),AIMessage(content=answer)])[-2*MAX_HISTORY_TURNS:]
        return dict(answer=answer,query=query,sources=passages)


def open_chat(vectors):
    from langchain_openai import ChatOpenAI
    from lab9_core.library import settings
    values = settings()
    model = ChatOpenAI(model=values.get('OPENAI_CHAT_MODEL','gpt-6-luna'),
        api_key=values.get('OPENAI_API_KEY'),use_responses_api=True,
        reasoning={'effort':'none'},max_tokens=2048,timeout=90,max_retries=2)
    return DocumentChat(model,vectors)
