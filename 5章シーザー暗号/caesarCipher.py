# シーザー暗号
import pyperclip

# 暗号化・復号する文字列
message = "drs3Gs3Gw9G3om2o4Gwo33kqoJ"

key = int(input("鍵を入力してください"))
# プログラムが暗号化するか複合化するか
mode = input("encryptかdecryptかを選択してください")

Symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz123456789 !?."

translated = ""

for symbol in message:
    if symbol in Symbols:
        symbol_index = Symbols.find(symbol)

        if mode == "encrypt":
            translated_index = symbol_index + key
        elif mode == "decrypt":
            translated_index = symbol_index - key
        
        if translated_index > len(Symbols):
            translated_index = translated_index - len(Symbols)
        elif translated_index < 0:
            translated_index = translated_index + len(Symbols)
        
        translated = translated + Symbols[translated_index]

    else:
        translated = translated + symbol

print(translated)
pyperclip.copy(translated)
