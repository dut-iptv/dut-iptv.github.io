import base64, hashlib, time, xbmc
from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util import Padding

class Credentials(object):
    def __init__(self):
        self.bs = 32
        self.crypt_key = self.uniq_id()

    def encode_credentials(self, username, password):
        encoded_username = ''
        encoded_password = ''

        if '' != username:
            encoded_username = self.encode(raw=username)

        if '' != password:
            encoded_password = self.encode(raw=password)

        return {
            'username': encoded_username,
            'password': encoded_password
        }

    def decode_credentials(self, username, password):
        decoded_username = ''
        decoded_password = ''

        if username and '' != username:
            decoded_username = self.decode(enc=username)

        if password and '' != password:
            decoded_password = self.decode(enc=password)

        return {
            'username': decoded_username,
            'password': decoded_password
        }

    def encode(self, raw):
        raw = bytes(Padding.pad(data_to_pad=raw.encode('utf-8'), block_size=self.bs))
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.crypt_key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decode(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.crypt_key, AES.MODE_CBC, iv)
        decoded = Padding.unpad(
            padded_data=cipher.decrypt(enc[AES.block_size:]),
            block_size=self.bs).decode('utf-8')
        return decoded

    def uniq_id(self, delay=1):
        mac_addr = self.get_mac_address(delay=delay)

        if ':' in mac_addr and delay == 2:
            return hashlib.sha256(str(mac_addr).encode()).digest()
        else:
            return hashlib.sha256('UnsafeStaticSecret'.encode()).digest()

    def get_mac_address(self, delay=1):
        mac_addr = xbmc.getInfoLabel('Network.MacAddress')
        i = 0

        while ':' not in mac_addr and i < 3:
            i += 1
            time.sleep(delay)
            mac_addr = xbmc.getInfoLabel('Network.MacAddress')

        return mac_addr