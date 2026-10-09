# 🎨 AutoDraw — Desenhista Automático para Windows

O **AutoDraw** é um aplicativo desktop para Windows (10/11) que reproduz imagens automaticamente através do mouse em programas de desenho como **Microsoft Paint, Krita, Photoshop, Paint.NET, GIMP** ou ferramentas web.

Mantendo a filosofia do projeto: **extremamente simples para o usuário, com qualidade de desenho e fidelidade totalmente configuráveis!**

---

## ✨ Recursos

1. **Seleção de Qualidade**:
   - **Baixa**: Prioriza velocidade, ideal para reprodução rápida aproximada.
   - **Média** *(Padrão)*: Equilíbrio entre fidelidade e tempo.
   - **Alta**: Máxima fidelidade e precisão de detalhes.
2. **Dois modos de desenho**:
   - **Contorno**: apenas as bordas da imagem.
   - **Preto e Branco**: bordas mais preenchimento hachurado das áreas escuras.
3. **Cálculo de Tempo Estimado**:
   - Modela o custo real de cada evento de mouse (`SendInput`), os delays por ponto e a quantidade de traços.
   - Exibe o tempo estimado antes de começar (ex: `⏱ Tempo estimado: ≈ 2m 35s`).
   - Durante o desenho, atualiza o **tempo restante** a partir da taxa medida de pontos por segundo.
   - **Auto-Calibração**: ajusta o estimador após cada desenho, sem acumular correções.
4. **Aviso de desenhos longos**: alerta antes de desenhos acima de um limite configurável de pontos.
5. **Drag & Drop**: arraste imagens direto do Windows Explorer para a janela.
6. **Formatos suportados**: `PNG` (com transparência composta sobre branco), `JPG`, `JPEG`, `BMP`, `WEBP`, `GIF` (primeiro frame), `SVG` (renderização vetorial com proporção preservada) e `TIFF`.
7. **Pré-visualização Tripla**: alternância entre *Resultado Processado*, *Imagem Original* e *Simulação no Paint*.
8. **Confirmação & Contagem Regressiva de 3s**, com opção `Não mostrar novamente` (reversível em ⚙️ Configurações).
9. **Tela de Conclusão & `🔄 REPETIR DESENHO`**: redesenha na mesma área, sempre passando pela contagem regressiva.
10. **Processamento Assíncrono**: toda a vetorização roda em `QThread` com cancelamento cooperativo, mantendo a interface fluida.
11. **Suporte a múltiplos monitores e telas com escala (DPI)**: a área é capturada em pixels físicos reais.

---

## 🚀 Como Usar (Passo a Passo)

1. **Abra o AutoDraw** (ou execute `dist/AutoDraw.exe`).
2. **Carregue uma imagem**: arraste para a janela ou clique em `📁 ESCOLHER IMAGEM`.
3. **Selecione a Qualidade e o Modo** nos dropdowns.
4. **Abra o programa de desenho** (ex: Microsoft Paint) e selecione o pincel desejado.
5. **Selecione a área na tela**:
   - Clique em `🖱️ SELECIONAR ÁREA DE DESENHO`.
   - Clique e arraste na tela para definir o retângulo onde o desenho aparecerá.
6. **Confira o tempo estimado e a simulação**.
7. **Clique em `▶ DESENHAR`**:
   - Após a contagem de 3 segundos, o AutoDraw assumirá o controle do mouse.
   - **Pressione ESC a qualquer momento para cancelar imediatamente**.

---

## 🛠️ Tecnologias Utilizadas

- **Interface Gráfica**: PySide6 (Qt6 for Python) + QtSvg
- **Processamento de Imagem**: OpenCV (`cv2`) + NumPy
- **Vetorização**: detecção Canny seguida de *tracing* direto das polilinhas (cada pixel de borda é visitado uma única vez) e simplificação Ramer-Douglas-Peucker
- **Otimização de Trajetórias**: vizinho mais próximo sobre grid espacial, com inversão dinâmica de traços
- **Densificação**: reamostragem vetorizada com NumPy, preservando os vértices originais
- **Automação do Mouse**: Win32 `SendInput` (coordenadas normalizadas no desktop virtual) + listener global de ESC (`pynput`)
- **Compilação**: PyInstaller Standalone `.exe`

---

## ▶️ Abrindo o AutoDraw

### Jeito mais simples: duplo clique em `AutoDraw.bat`

Não precisa abrir terminal nem digitar comando nenhum. O `.bat`:

- abre o `dist\AutoDraw.exe` se ele já tiver sido compilado;
- senão localiza o Python instalado, **instala as dependências na primeira vez** e abre o aplicativo;
- abre **sem janela de terminal** (usa o `pythonw.exe` do próprio interpretador encontrado);
- se não houver Python, explica onde baixá-lo.

> Quer um ícone na área de trabalho? Clique com o botão direito em `AutoDraw.bat` → *Enviar para* → *Área de trabalho (criar atalho)*.

### Gerar um `.exe` que roda sem Python

Duplo clique em `Compilar-EXE.bat` (ou `python build_exe.py`). O resultado vai para `dist\AutoDraw.exe` e funciona em qualquer Windows, mesmo sem Python instalado.

| Formato | Comando | Tamanho | Abertura |
|---|---|---|---|
| Arquivo único | `Compilar-EXE.bat` | maior | lenta (descompacta no `%TEMP%` a cada abertura) |
| Pasta | `Compilar-EXE.bat pasta` | menor por arquivo | **bem mais rápida** |

Depois de compilar, o `AutoDraw.bat` passa a abrir o executável automaticamente.

## 💻 Desenvolvimento

### Rodar via Código Fonte
```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
python main.py
```

### Testes e Lint
```bash
pip install -r requirements-dev.txt

pytest tests        # 210 testes
pyflakes main.py build_exe.py src tests
```

### Compilar Executável Standalone
```bash
python build_exe.py
```
O executável final será salvo em `dist/AutoDraw.exe`.

---

## 📁 Estrutura

```
AutoDraw.bat                Duplo clique para abrir (sem terminal)
Compilar-EXE.bat            Duplo clique para gerar dist\AutoDraw.exe
main.py                     Ponto de entrada (DPI awareness + QApplication)
build_exe.py                Script de empacotamento PyInstaller
src/
  config.py                 Preferências persistentes (escrita atômica + validação)
  logger.py                 Logging em arquivo (~/.autodraw/autodraw.log)
  image_loader.py           Carregamento de PNG/JPG/SVG/GIF/... em BGR
  image_processor.py        Pipeline: ajuste à área → bordas → densificação → ordenação
  contour_detector.py       Tracing de polilinhas e hachura vetorizada
  path_optimizer.py         Ordenação dos traços por grid espacial
  time_estimator.py         Estimativa, tempo restante e calibração
  mouse_controller.py       Win32 SendInput, DPI, ESC de emergência
  drawing_engine.py         QThread que executa o desenho
  async_processor.py        QThread de processamento com cancelamento
  ui/                       Janela principal, diálogos, overlay e widgets
tests/                      Suíte pytest
```

---

## 🔧 Dados do Usuário

Ficam em `%USERPROFILE%\.autodraw\`:

- `config.json` — preferências (qualidade, modo, velocidade, última área, calibração)
- `autodraw.log` — log rotativo da aplicação, útil para diagnosticar o `.exe` compilado

Defina a variável de ambiente `AUTODRAW_HOME` para usar outro diretório.
