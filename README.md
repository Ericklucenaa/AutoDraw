# 🎨 AutoDraw V2 — Desenhista Automático para Windows

O **AutoDraw V2** é um aplicativo desktop completo para Windows (10/11) que reproduz imagens automaticamente através do mouse em programas de desenho como **Microsoft Paint, Krita, Photoshop, Paint.NET, GIMP** ou ferramentas web.

Mantendo a filosofia do projeto: **extremamente simples para o usuário, com qualidade de desenho e fidelidade totalmente configuráveis!**

---

## ✨ Novidades da Versão 2

1. **Dropdown de Seleção de Qualidade**:
   - **Baixa**: Prioriza velocidade, ideal para reprodução rápida aproximada.
   - **Média** *(Padrão)*: Equilíbrio perfeito entre fidelidade e tempo.
   - **Alta**: Máxima fidelidade e precisão de detalhes.
2. **Cálculo Inteligente de Tempo Estimado**:
   - Calcula o tempo exato com base em distância percorrida pelo mouse, quantidade de traços, pontos e delays.
   - Exibe o tempo estimado antes de começar (ex: `⏱ Tempo estimado: ≈ 2m 35s`).
   - Durante o desenho, atualiza dinamicamente o **tempo restante em tempo real**!
   - **Auto-Calibração**: Ajusta o estimador automaticamente após cada desenho finalizado.
3. **Suporte a Drag & Drop (Arrastar e Soltar)**:
   - Arraste imagens diretamente do Windows Explorer para a janela do aplicativo!
4. **Formatos de Imagem Expandidos**:
   - `PNG` (com tratamento completo de transparência — fundo branco automático!), `JPG`, `JPEG`, `BMP`, `WEBP`, `GIF` (primeiro frame), `SVG` (renderização vetorial nativa) e `TIFF`.
5. **Pré-visualização Tripla (Dual Preview & Simulação)**:
   - Alternância rápida entre: *Resultado Processado*, *Imagem Original* e *Simulação no Paint*.
6. **Confirmação & Contagem Regressiva de 3s**:
   - Modal com resumo completo (imagem, dimensões, área, traços e tempo) + opção `☑ Não mostrar novamente`.
   - Contagem regressiva visual (`3... 2... 1... Começando!`).
7. **Tela de Conclusão & "REPETIR DESENHO"**:
   - Botão `🔄 REPETIR DESENHO` permite redesenhar na mesma área sem reconfigurar nada em 1 clique.
8. **Processamento Assíncrono (Sem travar a interface)**:
   - Toda a vetorização roda em segundo plano (`QThread`), garantindo interface 100% fluida ao alternar qualidades.

---

## 🚀 Como Usar (Passo a Passo)

1. **Abra o AutoDraw** (ou execute `dist/AutoDraw.exe`).
2. **Carregue uma imagem**: Arraste para a janela ou clique em `📁 ESCOLHER IMAGEM`.
3. **Selecione a Qualidade**: Escolha `Baixa`, `Média` ou `Alta` no dropdown.
4. **Abra o programa de desenho** (ex: Microsoft Paint) e selecione o pincel desejado.
5. **Selecione a área na tela**:
   - Clique em `🖱️ SELECIONAR ÁREA DE DESENHO`.
   - Clique e arraste na tela do Paint para definir o retângulo onde o desenho aparecerá.
6. **Confira o tempo estimado e a simulação**.
7. **Clique em `▶ DESENHAR`**:
   - Após a contagem de 3 segundos, o AutoDraw assumirá o controle do mouse.
   - **Pressione ESC a qualquer momento para cancelar imediatamente**.

---

## 🛠️ Tecnologias Utilizadas

- **Interface Gráfica**: PySide6 (Qt6 for Python) + QtSvg
- **Processamento de Imagem & Visão Computacional**: OpenCV (`cv2`) + NumPy
- **Otimização de Trajetórias**: TSP Greedy (Vizinho mais próximo com inversão dinâmica)
- **Vetorização Densa**: Interpolação de pontos pixel a pixel (`interpolate_stroke`)
- **Automação do Mouse**: Win32 API (`user32.dll`) + Listener Global da tecla ESC (`pynput`)
- **Compilação**: PyInstaller Standalone `.exe`

---

## 💻 Desenvolvimento & Execução

### Rodar via Código Fonte
```bash
# Instalar dependências
pip install PySide6 opencv-python pyautogui pynput pillow pytest

# Executar aplicação
python main.py

# Rodar testes unitários
pytest tests/
```

### Compilar Executável Standalone
```bash
python build_exe.py
```
O executável final será salvo em `dist/AutoDraw.exe`.
