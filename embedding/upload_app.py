"""Document upload and conversation interface for Part 3."""
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab9_core.library import FILE_TYPES, SourceFile, open_library
from lab9_core.conversation import open_chat
from lab9_core.errors import user_error

st.set_page_config(page_title='ADS Document Assistant',page_icon='📚')
st.title('ADS Document Assistant')


@st.cache_resource
def library():
    return open_library()


try:
    collection = library()
except Exception as error:
    st.error(f'Could not open the document library ({user_error(error)}). Check the local configuration.')
    st.stop()

with st.sidebar:
    st.header('Documents')
    selection = st.file_uploader('Select PDFs, text, or HTML',type=FILE_TYPES,accept_multiple_files=True)
    if st.button('Process',disabled=not selection):
        try:
            with st.spinner('Processing documents...'):
                documents = collection.ingest([SourceFile(item.name,item.getvalue()) for item in selection])
                st.session_state['chat'] = open_chat(collection.vectors)
                st.session_state['messages'] = []
            st.success(f'Processed {len(selection)} file(s): {len(documents)} chunks.')
        except Exception as error:
            st.error(f'Processing failed ({user_error(error)}). You can retry the selected files.')
    if st.button('Load saved index'):
        try:
            if not collection.vectors.load():
                raise FileNotFoundError('No saved index')
            st.session_state['chat'] = open_chat(collection.vectors)
            st.session_state['messages'] = []
            st.success('Saved index loaded.')
        except Exception as error:
            st.error(f'Could not load the index ({user_error(error)}).')
    if st.button('Clear conversation',disabled='chat' not in st.session_state):
        st.session_state['chat'].clear()
        st.session_state['messages'] = []
    st.caption('Stored documents')
    for filename,count in collection.database.list_sources():
        st.text(f'{filename} ({count} pages)')

def render_message(message):
    with st.chat_message(message['role']):
        st.markdown(message['text'])
        if message.get('sources'):
            with st.expander('Retrieved passages'):
                for i,passage in enumerate(message['sources'],1):
                    st.text(f"[{i}] {passage['filename']} | PDF page {passage['page']}")
                    st.text(passage['text'])


for message in st.session_state.get('messages',[]):
    render_message(message)

question = st.chat_input('Ask about your documents')
if question:
    if 'chat' not in st.session_state:
        st.warning('Process documents or load the saved index first.')
    else:
        try:
            with st.spinner('Retrieving passages...'):
                response = st.session_state['chat'].ask(question)
            messages=[dict(role='user',text=question),
                      dict(role='assistant',text=response['answer'],sources=response['sources'])]
            st.session_state.setdefault('messages',[]).extend(messages)
            for message in messages:
                render_message(message)
        except Exception as error:
            st.error(f'Question failed ({user_error(error)}); this turn was not saved.')
