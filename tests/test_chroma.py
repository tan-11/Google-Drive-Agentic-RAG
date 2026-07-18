import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

import pytest
from app.db.chroma import Chroma
import shutil
import tempfile

cm = Chroma("tests/chroma_data")

@pytest.fixture
def chroma_db():

    # create temporary folder
    temp_dir = tempfile.mkdtemp()

    db = Chroma(
        path=temp_dir
    )

    yield db

    # cleanup after test
    shutil.rmtree(temp_dir)


def test_upsert(chroma_db):
    documents = [
        "document1",
        "document2"
    ]

    embeddings = [
        [0.1,0.2,0.3],
        [1.0, 2.0, 3.0]
    ]

    metadatas = [
        {
            "file_id":"file1",
            "page":1
        },
        {
            "file_id":"file2",
            "page":1
        }
    ]

    ids = [
        "chunk1",
        "chunk2"
    ]

    chroma_db.upsert(
        documents,
        embeddings,
        metadatas,
        ids
    )

    count = chroma_db.collection.count()

    assert count == 2


def test_retrieve_similar_documents(chroma_db):

    chroma_db.upsert(
        [
            "input1",
            "input2"
        ],
        [
            [1.0, 0.2, 0.0],
            [0.3, 0.2, 0.2]
        ],
        [
            {"file_id":"file1"},
            {"file_id":"file2"}
        ],
        [
            "1",
            "2"
        ]
    )


    result = chroma_db.retrieve_similar_documents(
        query_embeddings=[
            [0.9,0.1,0]
        ],
        n_results=1
    )


    assert len(result["ids"][0]) == 1

    assert result["ids"][0][0] == "1"


def test_delete_rows_by_fileid(chroma_db):
    chroma_db.upsert(
        [
            "document A",
            "document B",
            "document A"
        ],
        [
            [1,0],
            [0,1],
            [0,1]
        ],
        [
            {
                "file_id":"A"
            },
            {
                "file_id":"B"
            },
            {
                "file_id":"A"
            }
        ],
        [
            "chunkA",
            "chunkB",
            "chunkA2"
        ]
    )

    chroma_db.delete_rows_by_fileid("A")

    count = chroma_db.collection.count()

    assert count == 1

    remaining = chroma_db.collection.get()

    assert remaining["ids"] == ["chunkB"]

def test_file_metadata(chroma_db):
    chroma_db.upsert(
        [
            "hello world"
        ],
        [
            [0.1,0.2]
        ],
        [
            {
                "file_id":"abc",
                "filename":"test.pdf"
            }
        ],
        [
            "chunk1"
        ]
    )

    result = chroma_db.collection.get(
        where={
            "file_id":"abc"
        }
    )

    assert result["metadatas"][0]["filename"]=="test.pdf"
