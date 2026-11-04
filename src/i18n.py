"""
Interface languages: Portuguese (source), English and Spanish.

Every user-facing string is written in Portuguese in the code and wrapped in
tr(); the Portuguese text is the lookup key. Placeholders use str.format
syntax, so tr("Traço: {current:,}", current=5) works in every language.
A missing translation falls back to the Portuguese text instead of failing,
and tests/test_i18n.py checks that every tr() key has both translations.
"""
import locale
from typing import Dict, Tuple

# Windows does not draw flag emoji (they show up as "BR", "US"), so names only.
LANGUAGES: Dict[str, str] = {"pt": "Português", "en": "English", "es": "Español"}
DEFAULT_LANGUAGE = "pt"

_current = DEFAULT_LANGUAGE


def set_language(code: str) -> str:
    """Selects the interface language; unknown codes fall back to Portuguese."""
    global _current
    _current = code if code in LANGUAGES else DEFAULT_LANGUAGE
    return _current


def get_language() -> str:
    return _current


def detect_language() -> str:
    """Language of the Windows/user locale, when it is one we ship."""
    try:
        from PySide6.QtCore import QLocale

        name = QLocale.system().name()
    except Exception:  # pragma: no cover - Qt missing
        name = locale.getlocale()[0] or ""
    code = (name or "").lower()[:2]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def tr(text: str, **values) -> str:
    """Translates a Portuguese source string and fills in its placeholders."""
    if _current != DEFAULT_LANGUAGE:
        pair = TRANSLATIONS.get(text)
        if pair is not None:
            text = pair[0] if _current == "en" else pair[1]
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text
    return text


# Portuguese source -> (English, Spanish)
TRANSLATIONS: Dict[str, Tuple[str, str]] = {
    # ---- main window
    "AutoDraw — Desenhista Automático": ("AutoDraw — Automatic Drawer", "AutoDraw — Dibujante Automático"),
    "Transforme qualquer imagem em traços automáticos.": (
        "Turn any image into automatic strokes.", "Convierte cualquier imagen en trazos automáticos."),
    "Idioma": ("Language", "Idioma"),
    "Como usar (tutorial)": ("How to use (tutorial)", "Cómo usar (tutorial)"),
    "Apoiar o projeto (Ko-fi)": ("Support the project (Ko-fi)", "Apoyar el proyecto (Ko-fi)"),
    "Configurações": ("Settings", "Configuración"),
    "Escolha a imagem": ("Choose the image", "Elige la imagen"),
    "Ajuste o desenho": ("Adjust the drawing", "Ajusta el dibujo"),
    "Marque a área no programa de desenho": ("Mark the area in your drawing app", "Marca el área en tu programa de dibujo"),
    "Desenhe": ("Draw", "Dibuja"),
    "📁 ESCOLHER IMAGEM": ("📁 CHOOSE IMAGE", "📁 ELEGIR IMAGEN"),
    "Nenhuma imagem selecionada": ("No image selected", "Ninguna imagen seleccionada"),
    "🎨 Resultado": ("🎨 Result", "🎨 Resultado"),
    "🖼️ Original": ("🖼️ Original", "🖼️ Original"),
    "📐 Simulação": ("📐 Preview", "📐 Simulación"),
    "Qualidade:": ("Quality:", "Calidad:"),
    "Modo:": ("Mode:", "Modo:"),
    "Baixa": ("Low", "Baja"),
    "Média": ("Medium", "Media"),
    "Alta": ("High", "Alta"),
    "Contorno": ("Outline", "Contorno"),
    "Preto e Branco": ("Black & White", "Blanco y Negro"),
    "Contorno: apenas as bordas da imagem.\nPreto e Branco: bordas mais preenchimento hachurado das áreas escuras.": (
        "Outline: only the edges of the image.\nBlack & White: edges plus hatched fill of the dark areas.",
        "Contorno: solo los bordes de la imagen.\nBlanco y Negro: bordes más relleno rayado de las zonas oscuras."),
    "Ajuste da imagem:": ("Image fit:", "Ajuste de la imagen:"),
    "Manter proporção": ("Keep proportions", "Mantener proporción"),
    "Preencher área": ("Fill area", "Rellenar área"),
    "Esticar": ("Stretch", "Estirar"),
    "Velocidade:": ("Speed:", "Velocidad:"),
    "Lento": ("Slow", "Lento"),
    "Rápido": ("Fast", "Rápido"),
    "Simplificar imagem (remover ruídos pequenos)": (
        "Simplify image (remove small noise)", "Simplificar imagen (quitar ruido pequeño)"),
    "🖱️ SELECIONAR ÁREA": ("🖱️ SELECT AREA", "🖱️ SELECCIONAR ÁREA"),
    "Área: ❌ Não selecionada": ("Area: ❌ Not selected", "Área: ❌ No seleccionada"),
    "Área: {w}×{h} px em ({x}, {y})": ("Area: {w}×{h} px at ({x}, {y})", "Área: {w}×{h} px en ({x}, {y})"),
    "⏱ Tempo estimado: --": ("⏱ Estimated time: --", "⏱ Tiempo estimado: --"),
    "⏱ Tempo estimado: ≈ {time}": ("⏱ Estimated time: ≈ {time}", "⏱ Tiempo estimado: ≈ {time}"),
    "Aguardando seleção de imagem e área...": (
        "Waiting for an image and an area...", "Esperando una imagen y un área..."),
    "⏱ Analisando imagem...": ("⏱ Analyzing image...", "⏱ Analizando imagen..."),
    "Calculando trajetórias...": ("Calculating paths...", "Calculando trayectorias..."),
    "❌ Falha ao processar a imagem.": ("❌ Failed to process the image.", "❌ Error al procesar la imagen."),
    "Traços: {strokes:,} | Pontos: {points:,} | Qualidade: {quality}": (
        "Strokes: {strokes:,} | Points: {points:,} | Quality: {quality}",
        "Trazos: {strokes:,} | Puntos: {points:,} | Calidad: {quality}"),
    "⚠️ Desenho muito longo: {points:,} pontos (≈ {time}). Reduza a qualidade ou a área para terminar mais rápido.": (
        "⚠️ Very long drawing: {points:,} points (≈ {time}). Lower the quality or the area to finish sooner.",
        "⚠️ Dibujo muy largo: {points:,} puntos (≈ {time}). Baja la calidad o el área para terminar antes."),
    "▶ DESENHAR": ("▶ DRAW", "▶ DIBUJAR"),
    "☕ Apoie o AutoDraw": ("☕ Support AutoDraw", "☕ Apoya AutoDraw"),
    "O AutoDraw é grátis e de código aberto. Se ele te ajudou, considere fazer uma doação.": (
        "AutoDraw is free and open source. If it helped you, consider making a donation.",
        "AutoDraw es gratis y de código abierto. Si te ayudó, considera hacer una donación."),
    "💜 APOIAR NO KO-FI": ("💜 SUPPORT ON KO-FI", "💜 APOYAR EN KO-FI"),
    "⚡ ESC cancela o desenho · mexer ou clicar com o mouse pausa": (
        "⚡ ESC cancels the drawing · moving or clicking the mouse pauses it",
        "⚡ ESC cancela el dibujo · mover o hacer clic con el ratón lo pausa"),
    "Escolher imagem para AutoDraw": ("Choose an image for AutoDraw", "Elegir imagen para AutoDraw"),
    "Imagens suportadas": ("Supported images", "Imágenes compatibles"),
    "Todos os arquivos": ("All files", "Todos los archivos"),
    "Não foi possível abrir a imagem": ("Could not open the image", "No se pudo abrir la imagen"),
    "Erro desconhecido.": ("Unknown error.", "Error desconocido."),
    "Formato não suportado": ("Unsupported format", "Formato no compatible"),
    "❌ Formato de imagem não suportado.\n\nAceitos: {formats}": (
        "❌ Unsupported image format.\n\nAccepted: {formats}", "❌ Formato de imagen no compatible.\n\nAceptados: {formats}"),
    "Erro ao processar": ("Processing error", "Error al procesar"),
    "Não foi possível processar a imagem:\n\n{message}": (
        "Could not process the image:\n\n{message}", "No se pudo procesar la imagen:\n\n{message}"),
    "Aviso": ("Warning", "Aviso"),
    "Por favor, selecione uma imagem e uma área de desenho.": (
        "Please select an image and a drawing area.", "Selecciona una imagen y un área de dibujo."),
    "Desenho muito longo": ("Very long drawing", "Dibujo muy largo"),
    "Este desenho tem {points:,} pontos e deve levar cerca de {time}.\n\nO mouse ficará ocupado todo esse tempo. Deseja continuar?": (
        "This drawing has {points:,} points and should take about {time}.\n\nThe mouse will be busy the whole time. Continue?",
        "Este dibujo tiene {points:,} puntos y debería tardar unos {time}.\n\nEl ratón estará ocupado todo ese tiempo. ¿Continuar?"),
    "Cancelado": ("Cancelled", "Cancelado"),
    "O desenho foi cancelado: {reason}": ("The drawing was cancelled: {reason}", "El dibujo se canceló: {reason}"),
    "Erro": ("Error", "Error"),
    "Ocorreu um erro durante o desenho:\n{error}": (
        "An error occurred while drawing:\n{error}", "Ocurrió un error durante el dibujo:\n{error}"),
    "Recentes:": ("Recent:", "Recientes:"),
    "📥 SOLTE A IMAGEM AQUI": ("📥 DROP THE IMAGE HERE", "📥 SUELTA LA IMAGEN AQUÍ"),
    "🖼️ ARRASTE SUA IMAGEM AQUI": ("🖼️ DRAG YOUR IMAGE HERE", "🖼️ ARRASTRA TU IMAGEN AQUÍ"),
    "ou clique em 'Escolher imagem'": ("or click 'Choose image'", "o haz clic en 'Elegir imagen'"),
    " Simulação no Paint: {w}×{h} px ": (" Paint preview: {w}×{h} px ", " Simulación en Paint: {w}×{h} px "),
    # ---- area selection overlay
    " Área de desenho: {w} × {h} px ": (" Drawing area: {w} × {h} px ", " Área de dibujo: {w} × {h} px "),
    "Clique e arraste com o mouse para selecionar a área do desenho\n\n[ Pressione ESC para cancelar ]": (
        "Click and drag with the mouse to select the drawing area\n\n[ Press ESC to cancel ]",
        "Haz clic y arrastra con el ratón para seleccionar el área de dibujo\n\n[ Pulsa ESC para cancelar ]"),
    # ---- confirmation + countdown
    "Confirmar desenho — AutoDraw": ("Confirm drawing — AutoDraw", "Confirmar dibujo — AutoDraw"),
    "🎨 Seu desenho está pronto!": ("🎨 Your drawing is ready!", "🎨 ¡Tu dibujo está listo!"),
    "📄 <b>Imagem:</b> {name}": ("📄 <b>Image:</b> {name}", "📄 <b>Imagen:</b> {name}"),
    "📏 <b>Resolução:</b> {w} × {h} px": ("📏 <b>Resolution:</b> {w} × {h} px", "📏 <b>Resolución:</b> {w} × {h} px"),
    "⭐ <b>Qualidade:</b> {quality} &nbsp;·&nbsp; <b>Modo:</b> {mode}": (
        "⭐ <b>Quality:</b> {quality} &nbsp;·&nbsp; <b>Mode:</b> {mode}",
        "⭐ <b>Calidad:</b> {quality} &nbsp;·&nbsp; <b>Modo:</b> {mode}"),
    "📍 <b>Área selecionada:</b> {w} × {h} px": ("📍 <b>Selected area:</b> {w} × {h} px", "📍 <b>Área seleccionada:</b> {w} × {h} px"),
    "🖌️ <b>Traços:</b> {strokes:,} &nbsp;·&nbsp; <b>Pontos:</b> {points:,}": (
        "🖌️ <b>Strokes:</b> {strokes:,} &nbsp;·&nbsp; <b>Points:</b> {points:,}",
        "🖌️ <b>Trazos:</b> {strokes:,} &nbsp;·&nbsp; <b>Puntos:</b> {points:,}"),
    "⏱ <b>Tempo estimado:</b> ≈ {time}": ("⏱ <b>Estimated time:</b> ≈ {time}", "⏱ <b>Tiempo estimado:</b> ≈ {time}"),
    "⚠️ O AutoDraw assumirá o controle do mouse para desenhar.": (
        "⚠️ AutoDraw will take control of the mouse to draw.", "⚠️ AutoDraw tomará el control del ratón para dibujar."),
    "Certifique-se de que o programa de desenho esteja aberto na área selecionada.": (
        "Make sure your drawing app is open in the selected area.",
        "Asegúrate de que el programa de dibujo esté abierto en el área seleccionada."),
    "⚡ ESC cancela · mexer no mouse pausa o desenho.": (
        "⚡ ESC cancels · moving the mouse pauses the drawing.", "⚡ ESC cancela · mover el ratón pausa el dibujo."),
    "Não mostrar esta confirmação novamente": ("Don't show this confirmation again", "No mostrar esta confirmación de nuevo"),
    "Você pode reativá-la depois em ⚙️ Configurações.": (
        "You can turn it back on in ⚙️ Settings.", "Puedes volver a activarla en ⚙️ Configuración."),
    "CANCELAR": ("CANCEL", "CANCELAR"),
    "▶ COMEÇAR": ("▶ START", "▶ EMPEZAR"),
    "Prepare o programa de desenho...": ("Get your drawing app ready...", "Prepara el programa de dibujo..."),
    "O controle do mouse iniciará em breve\n[ ESC cancela ]": (
        "Mouse control starts shortly\n[ ESC cancels ]", "El control del ratón empezará en breve\n[ ESC cancela ]"),
    "Começando!": ("Starting!", "¡Empezando!"),
    # ---- progress + completion
    "AutoDraw — Desenhando...": ("AutoDraw — Drawing...", "AutoDraw — Dibujando..."),
    "🎨 Desenhando...": ("🎨 Drawing...", "🎨 Dibujando..."),
    "{percent}% concluído": ("{percent}% done", "{percent}% completado"),
    "Tempo restante: --": ("Time left: --", "Tiempo restante: --"),
    "Traço: {current:,} / {total:,}": ("Stroke: {current:,} / {total:,}", "Trazo: {current:,} / {total:,}"),
    "Tempo total estimado: {time}": ("Total estimated time: {time}", "Tiempo total estimado: {time}"),
    "Restante: {remaining}  ·  Decorrido: {elapsed}": (
        "Left: {remaining}  ·  Elapsed: {elapsed}", "Restante: {remaining}  ·  Transcurrido: {elapsed}"),
    "⏸️ PAUSAR": ("⏸️ PAUSE", "⏸️ PAUSAR"),
    "🛑 PARAR": ("🛑 STOP", "🛑 DETENER"),
    "▶️ CONTINUAR": ("▶️ CONTINUE", "▶️ CONTINUAR"),
    "⏸️ Desenho pausado": ("⏸️ Drawing paused", "⏸️ Dibujo en pausa"),
    "⚡ ESC cancela · mexer ou clicar com o mouse pausa o desenho": (
        "⚡ ESC cancels · moving or clicking the mouse pauses the drawing",
        "⚡ ESC cancela · mover o hacer clic con el ratón pausa el dibujo"),
    "Pausado: {reason}.": ("Paused: {reason}.", "En pausa: {reason}."),
    "Clique em CONTINUAR e solte o mouse: o desenho volta do mesmo ponto.": (
        "Click CONTINUE and let go of the mouse: the drawing resumes from the same point.",
        "Haz clic en CONTINUAR y suelta el ratón: el dibujo sigue desde el mismo punto."),
    "mouse mexido": ("mouse moved", "ratón movido"),
    "clique do mouse": ("mouse click", "clic del ratón"),
    "Interrompido pelo usuário (ESC)": ("Stopped by the user (ESC)", "Interrumpido por el usuario (ESC)"),
    "Parado pelo usuário": ("Stopped by the user", "Detenido por el usuario"),
    "🎉 Desenho concluído!": ("🎉 Drawing finished!", "🎉 ¡Dibujo terminado!"),
    "⏱ <b>Tempo real utilizado:</b> {time}": ("⏱ <b>Actual time:</b> {time}", "⏱ <b>Tiempo real:</b> {time}"),
    "⭐ <b>Qualidade:</b> {quality}": ("⭐ <b>Quality:</b> {quality}", "⭐ <b>Calidad:</b> {quality}"),
    "🖌️ <b>Traços realizados:</b> {strokes:,}": ("🖌️ <b>Strokes drawn:</b> {strokes:,}", "🖌️ <b>Trazos realizados:</b> {strokes:,}"),
    " &nbsp;·&nbsp; <b>Pontos:</b> {points:,}": (" &nbsp;·&nbsp; <b>Points:</b> {points:,}", " &nbsp;·&nbsp; <b>Puntos:</b> {points:,}"),
    "🆕 NOVO DESENHO": ("🆕 NEW DRAWING", "🆕 NUEVO DIBUJO"),
    "🔄 REPETIR DESENHO": ("🔄 DRAW AGAIN", "🔄 REPETIR DIBUJO"),
    "Redesenha na mesma área, com nova contagem regressiva.": (
        "Draws again in the same area, after a new countdown.", "Vuelve a dibujar en la misma área, con una nueva cuenta atrás."),
    # ---- settings
    "Configurações — AutoDraw": ("Settings — AutoDraw", "Configuración — AutoDraw"),
    "⚙️ Configurações": ("⚙️ Settings", "⚙️ Configuración"),
    "Geral": ("General", "General"),
    "Confirmar antes de começar": ("Confirm before starting", "Confirmar antes de empezar"),
    "Mostra o resumo do desenho antes de assumir o mouse.\nDesmarcado automaticamente se você usar 'Não mostrar novamente'.": (
        "Shows the drawing summary before taking over the mouse.\nUnchecked automatically if you use \"Don't show again\".",
        "Muestra el resumen del dibujo antes de tomar el ratón.\nSe desmarca solo si usas 'No mostrar de nuevo'."),
    "Mostrar janela de progresso": ("Show progress window", "Mostrar ventana de progreso"),
    "Tocar som ao terminar": ("Play a sound when done", "Reproducir un sonido al terminar"),
    "Padrões de desenho": ("Drawing defaults", "Valores por defecto"),
    "Contorno: apenas as bordas.\nPreto e Branco: bordas + preenchimento hachurado.": (
        "Outline: only the edges.\nBlack & White: edges + hatched fill.", "Contorno: solo los bordes.\nBlanco y Negro: bordes + relleno rayado."),
    "Modo padrão:": ("Default mode:", "Modo por defecto:"),
    "Qualidade padrão:": ("Default quality:", "Calidad por defecto:"),
    "Velocidade padrão:": ("Default speed:", "Velocidad por defecto:"),
    "desativado": ("off", "desactivado"),
    "Avisa antes de desenhos muito longos.\nQualidade Alta em áreas grandes passa facilmente de 1 milhão de pontos.": (
        "Warns before very long drawings.\nHigh quality on large areas easily goes past 1 million points.",
        "Avisa antes de dibujos muy largos.\nLa calidad Alta en áreas grandes supera fácilmente 1 millón de puntos."),
    "Avisar acima de (pontos):": ("Warn above (points):", "Avisar por encima de (puntos):"),
    "Calibração do estimador: ×{factor:.2f}  ·  Log: {path}": (
        "Estimator calibration: ×{factor:.2f}  ·  Log: {path}", "Calibración del estimador: ×{factor:.2f}  ·  Log: {path}"),
    "Restaurar padrões": ("Restore defaults", "Restaurar valores"),
    "Volta todas as opções desta janela aos valores originais.": (
        "Resets every option in this window to its original value.", "Devuelve todas las opciones de esta ventana a sus valores originales."),
    "Cancelar": ("Cancel", "Cancelar"),
    "Salvar": ("Save", "Guardar"),
    # ---- tutorial
    "Como usar o AutoDraw": ("How to use AutoDraw", "Cómo usar AutoDraw"),
    "Passo {n} de {total}": ("Step {n} of {total}", "Paso {n} de {total}"),
    "Pular": ("Skip", "Saltar"),
    "◀ Anterior": ("◀ Back", "◀ Anterior"),
    "Próximo ▶": ("Next ▶", "Siguiente ▶"),
    "Começar a usar ✓": ("Start using it ✓", "Empezar a usar ✓"),
    "Escolha uma imagem": ("Choose an image", "Elige una imagen"),
    "Arraste uma imagem para a janela ou clique em ESCOLHER IMAGEM. Funciona com PNG, JPG, SVG, GIF e outros formatos.": (
        "Drag an image into the window or click CHOOSE IMAGE. Works with PNG, JPG, SVG, GIF and other formats.",
        "Arrastra una imagen a la ventana o haz clic en ELEGIR IMAGEN. Funciona con PNG, JPG, SVG, GIF y otros formatos."),
    "Escolha a qualidade e o modo. Contorno desenha só as bordas; Preto e Branco também preenche as áreas escuras. Use as abas para ver como vai ficar.": (
        "Pick the quality and the mode. Outline draws only the edges; Black & White also fills the dark areas. Use the tabs to preview the result.",
        "Elige la calidad y el modo. Contorno dibuja solo los bordes; Blanco y Negro también rellena las zonas oscuras. Usa las pestañas para ver cómo quedará."),
    "Abra o Paint (ou outro programa), escolha o pincel e clique em SELECIONAR ÁREA. Depois arraste o mouse sobre a tela de desenho.": (
        "Open Paint (or another app), pick the brush and click SELECT AREA. Then drag the mouse over the canvas.",
        "Abre Paint (u otro programa), elige el pincel y haz clic en SELECCIONAR ÁREA. Luego arrastra el ratón sobre el lienzo."),
    "Desenhe e não mexa no mouse": ("Draw, and hands off the mouse", "Dibuja y no toques el ratón"),
    "Clique em DESENHAR e espere a contagem. Se você mexer no mouse, o desenho pausa; clique em CONTINUAR para seguir do mesmo ponto. ESC cancela a qualquer momento.": (
        "Click DRAW and wait for the countdown. If you move the mouse the drawing pauses; click CONTINUE to resume from the same point. ESC cancels at any time.",
        "Haz clic en DIBUJAR y espera la cuenta atrás. Si mueves el ratón, el dibujo se pausa; haz clic en CONTINUAR para seguir desde el mismo punto. ESC cancela en cualquier momento."),
    # ---- image loading errors
    "Nenhum arquivo informado.": ("No file given.", "No se indicó ningún archivo."),
    "Arquivo não encontrado:\n{path}": ("File not found:\n{path}", "Archivo no encontrado:\n{path}"),
    "Formato {ext} não suportado.\n\nAceitos: {formats}": (
        "Format {ext} is not supported.\n\nAccepted: {formats}", "Formato {ext} no compatible.\n\nAceptados: {formats}"),
    "A imagem está vazia ou corrompida:\n{name}": ("The image is empty or corrupted:\n{name}", "La imagen está vacía o dañada:\n{name}"),
    "SVG inválido ou não suportado:\n{name}": ("Invalid or unsupported SVG:\n{name}", "SVG no válido o no compatible:\n{name}"),
    "Não foi possível decodificar a imagem:\n{name}\n\n({error})": (
        "Could not decode the image:\n{name}\n\n({error})", "No se pudo decodificar la imagen:\n{name}\n\n({error})"),
    "Erro ao ler o arquivo:\n{name}\n\n({error})": ("Error reading the file:\n{name}\n\n({error})", "Error al leer el archivo:\n{name}\n\n({error})"),
}
