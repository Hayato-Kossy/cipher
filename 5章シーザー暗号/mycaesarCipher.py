#ASCIIコード48~122
def get_encrypt(target, key, cur_index, length, encrypted_target):
    if length <= cur_index:
        return encrypted_target
    return get_encrypt(target, key, cur_index + 1, length, encrypted_target + chr(ord(target[cur_index]) + key))

def get_decrypt(target, key, cur_index, length, decrypted_target):
    if length <= cur_index:
        return decrypted_target
    return get_decrypt(target, key, cur_index + 1, length, decrypted_target + chr(ord(target[cur_index]) - key))

if __name__ == '__main__':  
    target = input("暗号化もしくは復号化する対象を入力してください：　")
    key = int(input("鍵を入力してください：　"))
    mode = input("『暗号化』を行いますか『復合化』を行いますか：　")

    length = len(target)
    encrypted_target = ""
    decrypted_target = ""

    if mode == "暗号化":
        print(get_encrypt(target, key, 0, length, encrypted_target))
    elif mode == "復号化":
        print(get_decrypt(target, key, 0, length, decrypted_target))