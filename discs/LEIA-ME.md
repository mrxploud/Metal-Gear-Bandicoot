# discs/

Esta pasta fica **vazia no repositório**. Nenhum jogo é distribuído aqui: você precisa das suas próprias cópias.

São três discos de PlayStation, **nestas versões exatas** (os endereços, os nomes das entradas e os formatos só
foram conferidos nelas), em `.bin` + `.cue`, cada um na sua pasta:

| Jogo | Versão | Código | Para quê |
|---|---|---|---|
| Metal Gear Solid: Integral, disco 1 | Japão (En, Ja) | **SLPM-86247** | é o mundo: o jogo que é recompilado e remontado com o Crash dentro |
| Crash Bandicoot 3: Warped | Europa / Austrália | **SCES-01420** | o Crash jogável (modelo, animações, caixas, Aku Aku, bazuca, sons) |
| Crash Bandicoot | EUA | **SCUS-94900** | o "Woah!", o som do giro e o bipe da TNT (e o Crash dos testes 1 a 4) |

O MGS precisa ser o Integral japonês porque é a versão que o
[mgs_reversing](https://github.com/FoxdieTeam/mgs_reversing) descompila. Os discos 2 e 3 do Integral não são usados.

Os leitores de disco do projeto (`crash_assets/crashlib/disco.py` e `motor/montar_disco.py`) leem `.cue` + `.bin` com
setores de 2352 bytes. **Não leem `.chd`**: converta antes (`chdman extractcd`).
