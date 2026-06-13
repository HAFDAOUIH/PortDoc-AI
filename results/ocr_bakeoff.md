# OCR Bake-off — French scanned circular

Scored against ground truth (357 accented chars, 1593 words) recovered from the digital source pages of the Casablanca regulation. Run on CPU.

| Engine | Char similarity ↑ | Word error rate ↓ | Accents retained | Time |
|---|---|---|---|---|
| tesseract **(winner)** | 86.0% | 13.8% | 355/357 (99%) | 38s |
| easyocr | 26.4% | 34.7% | 322/357 (90%) | 77s |
| rapidocr | 52.1% | 36.4% | 160/357 (45%) | 24s |

**Verdict: tesseract.** Higher char-similarity and accent retention is what matters for downstream French retrieval — a mangled `matières`→`matieres` silently breaks sparse search.

## First 240 chars per engine (eyeball the accents)

**Ground truth:**
```
13 reglement d’exploitation du port de casablanca l’armateur ou l’agent maritime et/ou consignataire du bâtiment doit communiquer par la plate-forme d’échange des données informatisées du port (portnet) à la capitainerie du port et à l’expl
```
**tesseract:**
```
l'armateur ou l'agent maritime et/ou consignataire du bâtiment doit communiquer par la plate-forme d'échange des données informatisées du port (portnet) à la capitainerie du port et à l'exploitant, 48 heures au moins avant l'arrivée du bâti
```
**easyocr:**
```
larmateur ou fagent maritime etlou consignataire du bâtiment doit communiquer par la plate-forme déchange des données informatisées du port (portnet) à la capitainerie du port et à lexploitant; 48 heures au moins avant /arrivée du bâtiment 
```
**rapidocr:**
```
l'armateur ou l'agent maritime et/ou consignataire du batiment doit communiquer par la plate-forme d'échange des données informatisées du port (portnet) a la capitainerie du port et a 1'exploitant, 48 heures aumoins avantl'arrivéedubatiment
```
