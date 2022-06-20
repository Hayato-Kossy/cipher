import math
def get_encrypt(target, key, length, encrypted_target):
    for column in range(key):
        cur_index = column

        while cur_index < length:
            encrypted_target[column] += target[cur_index]
            cur_index += key

    return "".join(encrypted_target)

def get_decrypt(target, key, length, decrypted_target):
    columns = int(math.ceil(length) / float(key))
    rows = key

    column = 0
    row = 0
    shade = columns * rows - length

    for word in target:
        decrypted_target[column] += word
        column += 1

        if column == columns or column == columns - 1 and row >= rows - shade:
            column = 0
            row += 1
    
    return decrypted_target

if __name__ == '__main__':  
    target = input("暗号化もしくは復号化する対象を入力してください：　")
    key = int(input("鍵を入力してください：　"))
    mode = input("『暗号化』を行いますか『復合化』を行いますか：　")

    length = len(target)
    encrypted_target = [""] * key
    decrypted_target = [""] * int(math.ceil(length) / float(key))

    if mode == "暗号化":
        print(get_encrypt(target, key, length, encrypted_target))
    elif mode == "復号化":
        print(get_decrypt(target, key, length, decrypted_target))
