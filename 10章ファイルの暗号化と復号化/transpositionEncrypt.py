import pyperclip
def main():
    message = "Common sence is not so common"
    key = 8

    ciphertext = encryptMessage(key, message)
    print(ciphertext + '|')

    pyperclip.copy(ciphertext)

def encryptMessage(key, message):
    ciphertext = [''] * key

    for columun in range(key):
        currentIndex = columun

        while currentIndex < len(message):
            ciphertext[columun] += message[currentIndex]

            currentIndex += key

    return ''.join(ciphertext)

if __name__ == "__main__":
    main()