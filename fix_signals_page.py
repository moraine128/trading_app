import re

with open('main_enhanced.py', 'r') as f:
    lines = f.readlines()

# Finde die signals_page Funktion
start = None
end = None
for i, line in enumerate(lines):
    if 'async def signals_page(request: Request):' in line:
        start = i
    if start is not None and i > start and line.startswith('async def ') or (start is not None and i > start and line.startswith('@app.')):
        end = i
        break
if start is not None and end is None:
    end = len(lines)

# Ersetze die Funktion
new_function = '''async def signals_page(request: Request):
    """Signals Seite"""
    if templates:
        # Hole Unternehmensnamen für alle Ticker
        ticker_names = {ticker: get_ticker_name(ticker) for ticker in current_signals.keys()}
        return templates.TemplateResponse(
            "signals.html",
            {
                "request": request,
                "signals": current_signals,
                "config": current_config,
                "ticker_names": ticker_names
            }
        )
    else:
        return HTMLResponse("<h1>Signals</h1><p>Template nicht gefunden</p>")

'''

lines[start:end] = [new_function]

with open('main_enhanced.py', 'w') as f:
    f.writelines(lines)

print('Funktion korrigiert!')
