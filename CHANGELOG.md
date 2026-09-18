# Changelog

## [0.2.0] - 2026-09-19

### Aggiunto
- **La pagina di conferma mostra i dati censiti su ogni record.** Prima si
  vedevano solo il nome e quanti oggetti collegati sarebbero stati spostati:
  per scegliere quale record conservare servono i dati veri (telefono, email,
  data di nascita…). I campi che **differiscono fra i record** sono
  evidenziati, ed è su quelli che si rischia di perdere qualcosa.
- I campi mostrati seguono i `fieldsets` dell'admin, così i campi tecnici
  (token, contatori, flag interni) restano fuori. Si può decidere a mano con
  `merge_preview_fields`; `merge_preview_max_length` accorcia i valori lunghi.
- Suite di test (12) con un progetto di prova: il pacchetto non ne aveva.

### Modificato
- La tabella a quattro colonne è diventata una scheda per record: a 320 px
  quella tabella sforava lo schermo di 178 px. Su schermi larghi le schede
  stanno affiancate. Si sceglie il record toccando la scheda.

### Corretto
- **Unire verso il record privo di un valore unico falliva con
  `IntegrityError`.** Il travaso dei campi vuoti avveniva prima di eliminare
  i duplicati, quindi copiare per esempio un codice fiscale violava il
  vincolo di unicità: era il caso più comune, cioè conservare il record più
  recente. Ora i valori si leggono prima e si scrivono dopo la cancellazione;
  con `delete_duplicates=False` i campi unici vengono saltati.
- **La domanda di conferma non compariva mai.** Stava in un `onclick` in
  linea e il testo tradotto contiene un apostrofo («L'operazione»), che
  chiudeva la stringa JavaScript e rendeva il gestore non compilabile.

## [0.1.0]

- Prima versione: azione «Unisci selezionati…», bottone «Unisci con…» e
  fusione riflessiva delle relazioni.
