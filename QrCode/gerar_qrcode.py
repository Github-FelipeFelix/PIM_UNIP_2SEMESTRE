import qrcode

# A URL que o QR Code deve abrir (seu GitHub)
url_github = "https://github.com/Github-FelipeFelix/PIM_UNIP_2SEMESTRE#"

# Cria o objeto QR Code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)
qr.add_data(url_github)
qr.make(fit=True)

# Cria a imagem em preto e branco
img = qr.make_image(fill_color="black", back_color="white")

# Salva o arquivo final
img.save("qrcode_pim_github.png")