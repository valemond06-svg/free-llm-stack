# 08 · Sicurezza e rischi (leggere prima di iniziare)

## Antigravity: rischio ban reale

Il proxy Antigravity usa account Google in un modo non previsto da Google. Il suo stesso README
avverte che **Google sta bannando account collegati al proxy** (anche shadow-ban, senza avviso).

- Usa **solo account Google secondari**, mai quello con mail, Drive, foto, lavoro.
- Non usare account legati a Google Workspace aziendali o universitari.
- Considera ogni account Antigravity "a perdere". Lo stack funziona benissimo anche senza:
  i modelli Antigravity vengono semplicemente saltati.

## Free tier e termini di servizio

- FreeLLMAPI stesso dice: *uso personale e sperimentazione, non produzione*. I free tier non sono
  garantiti; per un prodotto vero passa a API a pagamento.
- I termini di ogni provider valgono anche se il traffico passa dal router.
- Più account per moltiplicare un free tier spesso viola i ToS (vedi [02](02-provider-e-account.md)).

## Privacy

I prompt passano da provider terzi gratuiti, alcuni dei quali possono usarli per training.
Non mandare segreti, credenziali, dati personali o codice proprietario sensibile tramite
`ask_freellmapi` / `model="auto"`. Le regole in `claude-code/CLAUDE.global.md` lo dicono a Claude.

## Segreti

| Segreto | Dove sta | Cosa NON fare |
|---|---|---|
| `ENCRYPTION_KEY` | `.env` (gitignored) + password manager | Perderla (key nel DB irrecuperabili) o committarla. |
| Unified key `freellmapi-…` | variabile d'ambiente utente, config MCP | Metterla in URL o in file del repo. Per client senza header usa i URL token revocabili (Keys → Agents). |
| Key dei provider | DB di FreeLLMAPI (cifrate AES-256-GCM) | Tenerle in file in chiaro oltre a `secrets/` temporaneo. |
| `secrets/freellmapi.config.json` | gitignored | Lasciarlo lì per sempre: dopo il primo avvio puoi cancellarlo. |
| Account proxy Antigravity | `data/antigravity/` o `~/.config/antigravity-proxy/` | Condividere quella cartella (contiene i token OAuth). |

Questo repo contiene **solo infrastruttura**: nessuna key, nessun DB, nessun token.
`.gitignore` esclude `.env`, `secrets/`, `data/`, `*.db`.

## Rete

- Tutte le porte sono su `127.0.0.1` di default. Tienile così.
- Accesso remoto: Tailscale o tunnel SSH. Mai `0.0.0.0` su una VPS senza firewall.
- FreeLLMAPI è single-user: chi ha la unified key usa tutte le tue quote.
