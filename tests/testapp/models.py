from django.db import models


class Cliente(models.Model):
    """Modello di prova: ha un campo unico, uno con scelte e delle relazioni."""

    LIVELLI = ((1, "Base"), (2, "Premium"))

    nome = models.CharField("Nome", max_length=50)
    # Il campo unico è il cuore della regressione: copiarlo da un duplicato
    # ancora vivo fa fallire l'unione.
    codice = models.CharField("Codice", max_length=20, unique=True, blank=True, null=True)
    email = models.EmailField("Email", blank=True)
    livello = models.IntegerField("Livello", choices=LIVELLI, default=1)
    note = models.TextField("Note", blank=True)
    interno = models.CharField("Campo interno", max_length=30, blank=True)

    def __str__(self):
        return self.nome


class Ordine(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="ordini")
    numero = models.CharField(max_length=10)

    def __str__(self):
        return self.numero
