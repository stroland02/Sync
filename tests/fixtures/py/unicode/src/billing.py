from stripe import StripeClient

"""Facturación para la región de España — cobros en euros."""

client = StripeClient("sk_test")


def cobrar(importe: int):
    # Créer une charge: le montant est en centimes (déjà converti).
    resultado = client.charges.create(amount=importe, currency="eur")
    return resultado.status
