import base64
import hashlib
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from Crypto.Cipher import AES


class WeComCryptoError(ValueError):
    pass


@dataclass(frozen=True)
class WeComEncryptedMessage:
    encrypt: str
    to_user_name: str | None = None


def verify_signature(token: str, signature: str, timestamp: str, nonce: str, encrypt: str) -> None:
    values = [token, timestamp, nonce, encrypt]
    digest = hashlib.sha1("".join(sorted(values)).encode("utf-8")).hexdigest()
    if digest != signature:
        raise WeComCryptoError("企业微信回调签名校验失败")


def decrypt_message(encoding_aes_key: str, corp_id: str, encrypt: str) -> str:
    aes_key = base64.b64decode(f"{encoding_aes_key}=")
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    decrypted = cipher.decrypt(base64.b64decode(encrypt))
    plain = _pkcs7_unpad(decrypted)
    msg_len = struct.unpack("!I", plain[16:20])[0]
    xml = plain[20 : 20 + msg_len].decode("utf-8")
    received_corp_id = plain[20 + msg_len :].decode("utf-8")
    if received_corp_id != corp_id:
        raise WeComCryptoError("企业微信 CorpID 校验失败")
    return xml


def parse_encrypted_xml(body: str) -> WeComEncryptedMessage:
    root = ET.fromstring(body)
    encrypt = root.findtext("Encrypt")
    if not encrypt:
        raise WeComCryptoError("企业微信回调缺少 Encrypt 字段")
    return WeComEncryptedMessage(encrypt=encrypt, to_user_name=root.findtext("ToUserName"))


def xml_to_dict(xml: str) -> dict:
    root = ET.fromstring(xml)

    def convert(node: ET.Element):
        children = list(node)
        if not children:
            return node.text
        data: dict[str, object] = {}
        for child in children:
            value = convert(child)
            if child.tag in data:
                existing = data[child.tag]
                if not isinstance(existing, list):
                    data[child.tag] = [existing]
                data[child.tag].append(value)
            else:
                data[child.tag] = value
        return data

    return {root.tag: convert(root)}


def _pkcs7_unpad(value: bytes) -> bytes:
    if not value:
        raise WeComCryptoError("企业微信消息为空")
    pad = value[-1]
    if pad < 1 or pad > 32:
        raise WeComCryptoError("企业微信消息填充无效")
    return value[:-pad]
