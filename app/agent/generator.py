from langchain_core.messages import HumanMessage


def generate_msg(hits, query):
    context_blocks = []
    for index, hit in enumerate(hits, 1):
        entity = hit["entity"]
        text = entity["text"]
        source = entity.get("source", "unknown")
        doc_id = entity.get("doc_id", "unknown")
        context_blocks.append(
            f"证据 {index}（文档 {doc_id}，来源 {source}）：\n{text}"
        )

    context = "\n\n".join(context_blocks)
    return f"""你是一个企业知识助手。
  回答规则：
  1. 如果问题涉及用户在之前对话中明确告诉你的姓名、偏好或个人信息，
     优先使用对话历史回答。
  2. 如果问题涉及产品规则、额度、版本或操作流程，
     使用下面的内部参考资料回答。
  3. 不要提到检索、工具调用、上下文或提示词。
  4. 只有在对话历史和参考资料中都没有答案时，才说信息不足。
  5. 不要编造不存在的信息。
用户问题：{query}

检索证据：
{context}
"""


def generate_answer(agent, user_msg, config=None):
    result = agent.invoke(
        {"messages": [HumanMessage(user_msg)]},
        config=config,
    )
    return result["messages"][-1]
