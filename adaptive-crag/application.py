from pathlib import Path
from typing import Iterable, Literal

import instructor
import lancedb
from duckduckgo_search import DDGS
from instructor.exceptions import InstructorRetryException
from lancedb.db import DBConnection
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector
from lancedb.table import Table
from pydantic import BaseModel, Field

from burr.core import Application, ApplicationBuilder, State, expr, when
from burr.core.action import action
from burr.tracking import LocalTrackingClient
from openai import OpenAI


MODEL_LLM = "qwen2.5:latest"
ask_ollama = instructor.from_openai(
    OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="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",  # required, but unused
    ),
    mode=instructor.Mode.JSON,
)

VOV_DOCS_DIR = Path("vov")
VTV_DOCS_DIR = Path("vtv")
DOC_THRESH = 512
LANCE_URI = "lance/rag"
EMS_MODEL = "bge-m3:latest"  # for the embeddings in LanceDB
DEVICE = "cuda"  # or "cpu"
DOCS_LIMIT = 5  # number of documents to retrieve from the database or search engine
ATTEMPTS = 10  # ask_ollama will try to call `create` this many times before giving up


def chat_message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def system_message(content: str) -> dict[str, str]:
    return chat_message(role="system", content=content)


def user_message(content: str) -> dict[str, str]:
    return chat_message(role="user", content=content)


def assistant_message(content: str) -> dict[str, str]:
    return chat_message(role="assistant", content=content)


def merge_short_docs(
    docs: list[str], file_name: str, doc_thresh: int = DOC_THRESH
) -> list[dict[str, str]]:
    """
    Merge short documents into longer ones for better performance.
    `file_name` is the name of the file the documents came from. It's just for metadata.
    """
    merged_docs = [{"text": docs[0], "file_name": file_name}]
    for doc in docs[1:]:
        last_text = merged_docs[-1]["text"]
        if len(last_text) <= doc_thresh:
            merged_docs[-1]["text"] = last_text.strip() + "\n" + doc
        else:
            merged_docs.append({"text": doc, "file_name": file_name})
    return merged_docs


def load_docs(
    file_names: list[str] | str | None = None,
    burr_docs_dir: Path = VOV_DOCS_DIR,
    doc_thresh: int = DOC_THRESH,
) -> list[dict[str, str]]:
    """
    Load strings from text files in `burr_docs_dir` and merge short documents.
    If `file_names` is None, load all files in the directory.
    """
    if file_names is None:
        files_iter = burr_docs_dir.glob("*.txt")
    elif isinstance(file_names, str):
        files_iter = [file_names]
    else:
        files_iter = file_names
    docs = []
    for file in files_iter:
        docs += merge_short_docs(
            docs=(burr_docs_dir / Path(file).name).with_suffix(".txt").read_text().split("\n\n"),
            file_name=Path(file).stem,
            doc_thresh=doc_thresh,
        )
    return docs


def add_table(
    db: DBConnection,
    table_name: str,
    data: list[dict[str, str]],
    schema: type[LanceModel],
) -> Table:
    """
    Drop the table if it exists, create a new table, add data, and create a Full-Text Search index.
    Semenaitc Search is enabled by default. So creating an FTS index makes the table Hybrid Search ready.
    Learn more about Hybrid Search in LanceDB: https://lancedb.github.io/lancedb/hybrid_search/hybrid_search/
    """
    db.drop_table(name=table_name, ignore_missing=True)  # type: ignore
    table = db.create_table(name=table_name, schema=schema)
    table.add(data=data)
    table.create_fts_index(field_names="text")  # type: ignore
    return table


def route_template(
    table_names: Iterable[str],
    query: str,
    chat_history: list[dict[str, str]] | None = None,
) -> str:
#     prompt = """\
# <task>
# You are a world-class router for user queries.
# Given a user query, you may need some extra information for answering the query. So you need to select the best place to find the answer.
# You have the following options:
# 1. You will have some vector database tables with information on specific topics. If the query is directly related to any of these topics, return the relevant table name.
# 2. If you can answer the query directly with your own knowledge, return "assistant".
# 3. If you don't have the answer to the query, you can search the internet for the answer. In this case, return "web_search".
# </task>

# <available_tables>
# """
    prompt = """\
<task>
Bạn là bộ định tuyến đẳng cấp thế giới cho các truy vấn của người dùng.
Với một truy vấn của người dùng trong thẻ <query>, bạn có thể cần một số thông tin bổ sung để trả lời truy vấn. Vì vậy, bạn cần chọn nơi tốt nhất để tìm câu trả lời.
Bạn có các tùy chọn sau:
1. Bạn sẽ có một số bảng cơ sở dữ liệu vectơ với thông tin về các chủ đề cụ thể nằm trong thẻ <available_tables> bên dưới. Nếu truy vấn liên quan trực tiếp đến bất kỳ chủ đề nào trong số này, hãy trả về tên bảng có liên quan.
2. Nếu bạn có thể trả lời truy vấn trực tiếp bằng kiến ​​thức của riêng mình, hãy trả về "trợ lý".
3. Nếu bạn không có câu trả lời cho truy vấn, bạn có thể tìm kiếm câu trả lời trên internet. Trong trường hợp này, hãy trả về "web_search".
</task>
<available_tables>
"""
    prompt += "\n".join(table_names)
    prompt += "\n</available_tables>"
    if chat_history:
        prompt += "\n\n<chat_history>\n"
        prompt += "\n".join(f"{msg['role']}: {msg['content']}" for msg in chat_history)
        prompt += "\n</chat_history>"
    prompt += f"\n\n<query>\n{query}\n</query>"
    return prompt


# used to get a structured response from the assistant when rewriting a query
class LanceDBQuery(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=10)
    query: str = Field(..., min_length=10, max_length=300)

    def __str__(self) -> str:
        return ", ".join(self.keywords) + ", " + self.query


def lancedb_query_template(query: str, chat_history: list[dict[str, str]]) -> str:
    """
    You are a world-class researcher with access to a vector database that can be one of or similar to ChromaDB, Weaviate, LanceDB, VertexAI, etc.
Given a user query, rewrite the query to find the most relevant information in the vector database.
Remember that the vector database has hybrid search capability, which means it can do both full-text search and vector similarity search.
So make sure to not remove any important keywords from the query. You can even add more keywords if you think they are relevant.
Split the query into a list of keywords and a string query.
    """
    prompt = f"""\
<task>
Bạn là một nhà nghiên cứu đẳng cấp thế giới có quyền truy cập vào cơ sở dữ liệu vectơ có thể là một trong những cơ sở dữ liệu như ChromaDB, Weaviate, LanceDB, VertexAI, v.v. hoặc tương tự.
Với một truy vấn người dùng trong thẻ <query>, hãy viết lại truy vấn để tìm thông tin có liên quan nhất trong cơ sở dữ liệu vectơ.
Hãy nhớ rằng cơ sở dữ liệu vectơ có khả năng tìm kiếm kết hợp, nghĩa là nó có thể thực hiện cả tìm kiếm full-text và tìm kiếm vector similarity.
Vì vậy, hãy đảm bảo không xóa bất kỳ từ khóa quan trọng nào khỏi truy vấn. Bạn thậm chí có thể thêm nhiều từ khóa hơn nếu bạn nghĩ rằng chúng có liên quan.
Chia truy vấn thành danh sách từ khóa và truy vấn chuỗi.
</task>

<query>
{query}
</query>
"""

    if chat_history:
        chat_history_str = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in chat_history]
        ).strip()
        prompt += f"\n<chat_history>\n{chat_history_str}\n</chat_history>"
    return prompt


# used to get a structured response from the assistant when extracting keywords for a web search
class ExaSearchKeywords(BaseModel):
    keywords: list[str] = Field(..., min_length=2, max_length=5)

    def __str__(self) -> str:
        return ", ".join(self.keywords)


def exa_search_query_template(query: str) -> str:
    """
    You are a world-class internet researcher.
Given a user query, extract 2-5 vietnamese keywords as queries for the web search. Including the topic background and main intent.
    """
    return f"""\
<task>
Bạn là một nhà nghiên cứu internet đẳng cấp thế giới.
Đưa ra một truy vấn của người dùng, trích xuất 2-5 từ khóa tiếng Việt làm truy vấn cho tìm kiếm trên web. Bao gồm bối cảnh chủ đề và mục đích chính.
</task>

<examples>

<query>
Đài tiếng nói Việt Nam được thành lập vào năm nào?
</query>
<keywords>
Đài tiếng nói Việt Nam, thành lập, năm
</keywords>

<query>
Hà Nội là thủ đô nước nào?
</query>
<keywords>
Hà Nội, thủ đô, nước
</keywords>

<query>
Liệt kê danh sách các kênh thuộc VTV.
</query>
<keywords>
danh sách, kênh, VTV
</keywords>

<query>
Đài truyền hình Việt Nam có tổng bao nhiêu kênh?
</query>
<keywords>
Đài truyền hình Việt Nam, kênh
</keywords>

<query>
Bạn hãy tóm tắt về lịch sử hình thành của đài vov
</query>
<keywords>
lịch sử, hình thành, đài vov
</keywords>

</examples>

<query>
{query}
</query>
"""


def evaluator_template(query: str, document: str) -> str:
    """
    You are a world-class document relevance evaluator.
Given a user query, does the following document have the exact information to answer the question? Answer True or False.
    """
    return f"""\
<task>
Bạn là người đánh giá mức độ liên quan của tài liệu đẳng cấp thế giới trong thẻ <document>.
Với một truy vấn của người dùng, tài liệu sau đây có thông tin chính xác để trả lời câu hỏi không? Trả lời True hoặc False.
</task>

<query>
{query}
</query>

<document>
{document}
</document>
"""


def get_user_query() -> str:
    query = ""
    while not query:
        query = input("(exit, quit, q to exit) > ").strip()
    return query


@action(reads=["db", "chat_history"], writes=["query", "route"])
def router(state: State, query: str, attempts: int = ATTEMPTS) -> tuple[dict[str, str], State]:
    """
    Route the user `query` to the appropriate place for an answer.
    If the `query` is directly related to a table in the database, return the table name.
    If a web search is needed, return "web_search".
    If the `query` can be directly answered by the assistant, return "assistant".
    If the `query` contains "exit", "quit", or "q", return "terminate".
    If there is a `chat_history`, it will also be used as context for the routing.
    If it fails to route after `attempts`, it will return "assistant".
    We use `Instructor` to ensure that the router only returns valid routes.
    """
    if query.lower() in ["exit", "quit", "q"]:
        route = "terminate"
        return {"route": route}, state.update(query=query, route=route)
    db: DBConnection = state["db"]
    table_names = db.table_names()
    chat_history = state["chat_history"]
    # using this as a `response_model` to ensure the route is valid
    routes = Literal[*table_names, "web_search", "assistant"]  # type: ignore
    try:
        route = ask_ollama.chat.completions.create(
            model=MODEL_LLM,
            messages=[
                user_message(
                    route_template(table_names=table_names, query=query, chat_history=chat_history)
                )  # type: ignore
            ],
            response_model=routes,  # type: ignore
            max_retries=attempts,
        )
    except Exception as e:
        print(f"Error in router: {e}")
        route = "assistant"
    return {"route": route}, state.update(query=query, route=route)  # type: ignore


@action(reads=["query", "chat_history"], writes=["lancedb_query"])
def rewrite_query_for_lancedb(
    state: State, rewrite_attempts: int = ATTEMPTS
) -> tuple[dict[str, str], State]:
    """
    Rewrite the user `query` to find the most relevant information in the LanceDB vector database.
    """
    query = state["query"]
    chat_history = state["chat_history"]
    try:
        query = str(
            ask_ollama.chat.completions.create(
                model=MODEL_LLM,
                messages=[
                    user_message(
                        lancedb_query_template(query=query, chat_history=chat_history)  # type: ignore
                    )
                ],
                response_model=LanceDBQuery,
                max_retries=rewrite_attempts,
            )
        )
    except Exception as e:
        print(f"Error in rewrite_query_for_lancedb: {e}")
    return {"lancedb_query": query}, state.update(lancedb_query=query)


@action(reads=["db", "route", "lancedb_query", "docs_limit"], writes=["lancedb_results"])
def search_lancedb(state: State) -> tuple[dict[str, list[str]], State]:
    db: DBConnection = state["db"]
    try:
        lancedb_results = (
            db.open_table(name=state["route"])
            .search(query=state["lancedb_query"], query_type="hybrid")
            .limit(limit=state["docs_limit"])
            .to_pandas()["text"]
            .tolist()
        )
    except Exception as e:
        print(f"Error in search_lancedb: {e}")
        lancedb_results = []
    return {"lancedb_results": lancedb_results}, state.update(lancedb_results=lancedb_results)


@action(reads=["query", "lancedb_results"], writes=["lancedb_results"])
def remove_irrelevant_lancedb_results(
    state: State,
) -> tuple[dict[str, list[str]], State]:
    """
    Ask the assistant to evaluate the relevance of each retrieved document with the user `query`.
    If the assistant thinks the document is relevant, keep it in the `lancedb_results`.
    """
    lancedb_results = state["lancedb_results"]
    if not lancedb_results:
        return {"lancedb_results": lancedb_results}, state
    filtered_results = []
    for lancedb_result in lancedb_results:
        try:
            is_relevant = ask_ollama.chat.completions.create(
                model=MODEL_LLM,
                messages=[
                    user_message(
                        evaluator_template(query=state["query"], document=lancedb_result)
                    )  # type: ignore
                ],
                response_model=bool,  # type: ignore
                max_retries=ATTEMPTS,
            )
        except Exception as e:
            print(f"Error in remove_irrelevant_lancedb_results: {e}")
            is_relevant = True
        if is_relevant:
            filtered_results.append(lancedb_result)
    return {"lancedb_results": filtered_results}, state.update(lancedb_results=filtered_results)


@action(reads=["query"], writes=["exa_search_keywords"])
def extract_keywords_for_exa_search(
    state: State, extraction_attempts: int = ATTEMPTS
) -> tuple[dict[str, str], State]:
    """
    Extract 2-5 keywords from the user `query` for a web search.
    These keywords will be used to search the internet for the answer. Instead of the full query.
    """
    query = state["query"]
    try:
        query = str(
            ask_ollama.chat.completions.create(
                model=MODEL_LLM,
                messages=[user_message(exa_search_query_template(query=query))],  # type: ignore
                response_model=ExaSearchKeywords,
                max_retries=extraction_attempts,
            )
        )
    except Exception as e:
        print(f"Error in extract_keywords_for_web_search: {e}")
    return {"exa_search_keywords": query}, state.update(exa_search_keywords=query)


# @action(reads=["exa_search_keywords", "docs_limit"], writes=["exa_search_results"])
# def search_exa(state: State) -> tuple[dict[str, list[str]], State]:
#     """
#     More details about the Exa API:
#         - https://docs.exa.ai/reference/getting-started
#         - https://github.com/exa-labs/exa-py
#     """
#     try:
#         exa_search_results = exa.search_and_contents(
#             query=state["exa_search_keywords"],
#             num_results=state["docs_limit"],
#             highlights=True,
#         )
#         exa_search_results = [res.highlights[0] for res in exa_search_results.results]
#     except Exception as e:
#         print(f"Error in search_exa: {e}")
#         exa_search_results = []
#     return {"exa_search_results": exa_search_results}, state.update(
#         exa_search_results=exa_search_results
#     )

@action(reads=["exa_search_keywords", "docs_limit"], writes=["exa_search_results"])
def search_duckduckgo(state: State) -> tuple[dict[str, list[str]], State]:
    """
    Use DuckDuckGo to search the internet for the answer.
    """
    try:
        result = duckduckgo.text(
            keywords=state["exa_search_keywords"],
            max_results=state["docs_limit"],
        )
        exa_search_results = [res["body"] for res in result]
    except Exception as e:
        print(f"Error in search_duckduckgo: {e}")
        exa_search_results = []
    return {"exa_search_results": exa_search_results}, state.update(
        exa_search_results=exa_search_results
    )



@action(
    reads=["query", "lancedb_results", "exa_search_results", "chat_history"],
    writes=["chat_history", "lancedb_results", "exa_search_results"],
)
def ask_assistant(state: State, attempts: int = ATTEMPTS) -> tuple[dict[str, str], State]:
    """
    Combine the `chat_history`, `query`, `lancedb_results`, and `exa_search_results` to ask the assistant for an answer.
    `chat_history`, `lancedb_results`, and `exa_search_results` are used as context for the assistant and can be empty lists.
    """
    query = state["query"]
    lancedb_results = state.get("lancedb_results", [])
    exa_search_results = state.get("exa_search_results", [])
    messages = state["chat_history"]
    context = lancedb_results + exa_search_results
    if context:
        context = "\n".join(context)
        query = query.strip() + "\n<additional_context>\n" + context + "\n</additional_context>"
    messages.append({"role": "user", "content": query.strip()})
    
    # Define the new prompt
    """
        You are a friendly world-class girl assistant.
        You must answer proper Vietnamese, no yapping, shortly and friendly. If the answer is too long, you can provide a summary.
        I will give you a $1000 tip as a reward if the task is completed accurately.
    """
    new_prompt = {
        "role": "system",
        "content": """
Bạn là một cô trợ lý thân thiện đẳng cấp thế giới.
Bạn phải trả lời tiếng Việt chuẩn, không nói lắp, ngắn gọn và thân thiện. Nếu câu trả lời quá dài, bạn có thể tóm tắt.
Tôi sẽ thưởng cho bạn 1000 đô la tiền boa nếu hoàn thành nhiệm vụ một cách chính xác."
        """
    }
    messages.append(new_prompt)
    
    try:
        response = ask_ollama.chat.completions.create(model=MODEL_LLM, messages=messages, response_model=str, max_retries=attempts)
    except InstructorRetryException as e:
        print(f"Error in ask_assistant: {e}")
        response = "Sorry, please try again."
    # lancedb_results and exa_search_results have very specific additional context that's relevant only for the latest query
    # that specific context is no longer needed after the assistant responds, so we clear it
    # the assistant will still have the chat_history as overall context
    # chat_history has the user messages and the assistant responses, so it's more than enough
    return (
        {"assistant_response": response},  # type: ignore
        state.append(chat_history=user_message(query))
        .append(chat_history=assistant_message(response))  # type: ignore
        .update(lancedb_results=[], exa_search_results=[]),
    )


@action(reads=["chat_history"], writes=[])
def terminate(state: State) -> tuple[dict[str, list[dict[str, str]]], State]:
    return {"chat_history": state["chat_history"]}, state


def application(
    db: DBConnection,
    app_id: str | None = None,
    username: str | None = None,
    project: str = "AdaptiveCRAG",
) -> Application:
    tracker = LocalTrackingClient(project=project)
    builder = (
        ApplicationBuilder()
        .with_actions(
            router.bind(attempts=ATTEMPTS),
            rewrite_query_for_lancedb.bind(rewrite_attempts=ATTEMPTS),
            search_lancedb,
            remove_irrelevant_lancedb_results,
            # extract_keywords_for_exa_search.bind(extraction_attempts=ATTEMPTS),
            # search_exa,
            # search_duckduckgo,
            ask_assistant.bind(attempts=ATTEMPTS),
            terminate,
        )
        .with_transitions(
            # if the user wants to exit the conversation
            ("router", "terminate", when(route="terminate")),  # type: ignore
            # if the `query` can be directly answered by the assistant
            ("router", "ask_assistant", when(route="assistant")),  # type: ignore
            # if a web search is needed
            # ("router", "extract_keywords_for_exa_search", when(route="web_search")),  # type: ignore
            # the database can have multiple tables for different topics
            # so it makes sense to have `when` conditions for all other routes and consider this as the default route
            # otherwise we would have to add a `when` condition for each table name
            ("router", "rewrite_query_for_lancedb"),
            ("rewrite_query_for_lancedb", "search_lancedb"),
            ("search_lancedb", "remove_irrelevant_lancedb_results"),
            # if there aren't enough relevant documents left after filtering
            # use web search to find more information
            # (
            #     "remove_irrelevant_lancedb_results",
            #     "extract_keywords_for_exa_search",
            #     # expr("len(lancedb_results) < docs_limit"),  # type: ignore
            #     expr("len(lancedb_results) < 1"),
            # ),
            # if there are enough relevant documents even after filtering, ask the assistant for an answer
            ("remove_irrelevant_lancedb_results", "ask_assistant"),
            # ("extract_keywords_for_exa_search", "search_duckduckgo"),
            # ("search_duckduckgo", "ask_assistant"),
            # go back to the router every time the assistant is done answering
            ("ask_assistant", "router"),
        )
        .with_tracker("local", project=project)
        .with_identifiers(app_id=app_id, partition_key=username)  # type: ignore
        .initialize_from(
            tracker,
            resume_at_next_action=True,
            default_entrypoint="router",
            default_state=dict(db=db, chat_history=[], docs_limit=DOCS_LIMIT),
        )
    )
    return builder.build()


if __name__ == "__main__":
    lance_model = get_registry().get("ollama").create(name=EMS_MODEL, device=DEVICE)

    # define the schema of your data using Pydantic
    class LanceDoc(LanceModel):
        text: str = lance_model.SourceField()
        vector: Vector(dim=lance_model.ndims()) = lance_model.VectorField()  # type: ignore
        file_name: str

    lance_db = lancedb.connect(LANCE_URI)

    vov = load_docs(burr_docs_dir=VOV_DOCS_DIR)
    vtv = load_docs(burr_docs_dir=VTV_DOCS_DIR)
    vov_table = add_table(db=lance_db, table_name="vov", data=vov, schema=LanceDoc)
    vtv_table = add_table(db=lance_db, table_name="vtv", data=vtv, schema=LanceDoc)

    app = application(db=lance_db)
    app.visualize(
        output_file_path="statemachine",
        include_conditions=True,
        include_state=False,
        format="png",
    )
    
    inputs = {"query": get_user_query()}
    while True:
        action, result, state = app.step(inputs=inputs)  # type:ignore
        print(f"\nRESULT: {result}\n")
        if action.name == "terminate":
            break
        elif action.name == "ask_assistant":
            inputs = {"query": get_user_query()}
