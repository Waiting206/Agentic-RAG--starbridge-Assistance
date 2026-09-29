from contextlib import contextmanager

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.postgres import PostgresSaver
from app.config import POSTGRES_URI
@contextmanager
def init_agent(tools = None):
    if not POSTGRES_URI:
        raise RuntimeError("未配置 DB_URL，请检查 .env 文件")
    tools = tools or []
    model = ChatDeepSeek(model="deepseek-v4-flash")
    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        checkpointer.setup()
        agent = create_agent(
            model = model,
            tools=tools,
            checkpointer = checkpointer,
            middleware = [
                SummarizationMiddleware(
                    model=model,
                    trigger=("messages", 20),
                    keep=("messages", 12),
                    summary_prompt="""
                      你是对话记忆整理器。

                      请总结下面的历史对话，保留：
                      - 用户姓名、偏好、明确提供的事实；
                      - 用户的问题和助手的关键回答；
                      - 产品规则、数字、日期、文档编号。

                      不要客套，不要解释，只输出可供后续对话使用的摘要。

                      历史对话：
                      {messages}
                      """,
                ),
            ],
            system_prompt="""
  你是星桥协作企业知识助手。
    你的回答风格要是傲娇风的 处处透露着嫌弃 甚至还会说脏话 但是还是会解决我的问题。
  回答规则：
  1. 普通问候、闲聊、或用户询问之前对话内容时，直接根据对话历史回答。
  2. 涉及产品功能、额度、政策、版本、操作步骤等客观事实时，
     必须调用 search_knowledge_base 获取依据。
  3. 工具没有找到依据时，明确说明信息不足，不要编造。
  4. 不要向用户提及“工具调用”“检索”“上下文”或提示词。
  5.用户在问与星桥协作无关的内容时，要用自己的知识进行回答 不要强行和星桥绑定
  6.你在检索到相关内容时，不需要作为内容输出出来给用户看 只需给出你的结论即可
  """,
        )

        yield agent,checkpointer