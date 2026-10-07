"""Text-only model transport preserving message and tool-call identities."""
from langchain_openai import ChatOpenAI


TEXT_PROFILE = dict(image_inputs=False, audio_inputs=False, video_inputs=False,
                    pdf_inputs=False, image_tool_message=False, pdf_tool_message=False)
ATTACHMENT_NOTICE = '[Attachment not sent: this gateway accepts text only. Use container tools to inspect the file.]'


def text_content(content):
    if not isinstance(content, list):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str):
            parts.append(block['text'])
        else:
            # Do not serialize binary data, URLs, or unknown block metadata as
            # prose. The explicit notice avoids claiming the model saw them.
            parts.append(ATTACHMENT_NOTICE)
    return '\n'.join(parts)


class TextGatewayChatOpenAI(ChatOpenAI):
    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        payload['messages'] = [dict(message, content=text_content(message['content']))
            if 'content' in message else message for message in payload['messages']]
        return payload
