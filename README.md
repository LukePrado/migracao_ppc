# migracao_ppc

App para alunos de Estatística da UFPB compararem o PPC 2013 com o novo PPC
(Resolução CONSEPE 41/2026). Contexto, regras e roteiro: `CLAUDE.md`.

## Rodar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # só o app
pip install -r requirements-dev.txt    # app + testes
streamlit run app/streamlit_app.py
```

## Testar

```bash
python scripts/validate_data.py
pytest
```
