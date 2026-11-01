"""Ingest a document folder or chat with the persistent upload library."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab9_core.library import FILE_TYPES, SourceFile, open_library
from lab9_core.conversation import open_chat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,help='Extract and store supported files recursively')
    parser.add_argument('--show-context',action='store_true')
    args = parser.parse_args()
    library = open_library()
    if args.folder:
        if not args.folder.is_dir():
            parser.error('The document folder does not exist')
        paths = sorted(p for p in args.folder.rglob('*') if p.is_file() and p.suffix.lstrip('.').lower() in FILE_TYPES)
        documents = library.ingest([SourceFile.from_path(path) for path in paths])
        print(f'Stored {len(paths)} file(s), {len(documents)} chunks.')
    if library.vectors.index is None:
        parser.error('No saved index; ingest documents first')
    chat = open_chat(library.vectors)
    print('Document RAG ready. Type exit to quit; /clear clears memory.')
    while True:
        try:
            question = input('You> ').strip()
        except (EOFError,KeyboardInterrupt):
            break
        if question.lower()=='exit':
            break
        if question=='/clear':
            chat.clear();print('Conversation memory cleared.');continue
        if not question:
            continue
        try:
            result = chat.ask(question)
            print(result['answer'])
            if args.show_context:
                for source in result['sources']:
                    print(f"{source['filename']} | PDF page {source['page']}\n{source['text']}")
        except Exception as error:
            print(f'Question failed ({type(error).__name__}); retry when ready.')
    print('Goodbye.')


if __name__=='__main__':
    main()
