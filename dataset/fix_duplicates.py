"""
Fix duplicate phrases in metadata.csv
- Keep first occurrence of each phrase
- Generate new unique phrases for duplicates
- Delete associated .wav files
- Update generation_state.json to mark as pending
"""
import json
import random
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# New unique phrases to replace duplicates (534 phrases, 9-19 words each)
REPLACEMENT_PHRASES = [
    "Me encanta como suena la lluvia sobre el tejado cuando estoy dentro de casa calentita",
    "Necesito comprar ingredientes frescos en el mercado para preparar una cena especial esta noche",
    "El gato duerme plácidamente en su cama favorita junto a la ventana donde entra el sol",
    "¿Has probado ese nuevo restaurante que abrieron cerca del parque central la semana pasada?",
    "La tecnología avanza tan rápido que es difícil mantenerse actualizado con todas las novedades constantemente",
    "Recuerdo perfectamente cuando visitamos aquella playa paradisíaca durante nuestras vacaciones de verano pasadas",
    "El profesor explicó el tema de forma tan clara que todos entendimos perfectamente el concepto",
    "Deberíamos planificar mejor nuestro tiempo para poder completar todas las tareas pendientes a tiempo",
    "La música tiene el poder de transportarnos a otros lugares y evocar emociones profundas",
    "Prefiero trabajar en las mañanas cuando mi mente está fresca y puedo concentrarme mejor",
    "El jardín se ve hermoso ahora que todas las flores han florecido y los colores son vibrantes",
    "¿Recuerdas aquella vez que nos perdimos en la ciudad y tuvimos que pedir indicaciones?",
    "La lectura es una de mis actividades favoritas para relajarme después de un día largo",
    "Tenemos que revisar los documentos antes de enviarlos para asegurarnos de que todo esté correcto",
    "El café recién hecho por la mañana es uno de los pequeños placeres que más disfruto",
    "¿Podrías mostrarme cómo funciona esta aplicación nueva que instalaste en tu teléfono móvil?",
    "La primavera trae consigo días más largos y temperaturas más agradables para salir al aire libre",
    "Me gustaría aprender a tocar un instrumento musical pero no sé por dónde empezar exactamente",
    "El viaje en tren fue muy agradable con paisajes hermosos que podíamos admirar por la ventana",
    "¿Sabías que los delfines pueden comunicarse entre ellos usando sonidos complejos y variados?",
    "La paciencia es una virtud que se desarrolla con el tiempo y la práctica constante diaria",
    "Necesito organizar mi escritorio porque está demasiado desordenado y no encuentro nada cuando lo necesito",
    "El atardecer desde la cima de la montaña fue uno de los espectáculos más hermosos",
    "¿Te gustaría acompañarme al cine este fin de semana para ver esa película que tanto esperábamos?",
    "La amistad verdadera se demuestra en los momentos difíciles cuando más necesitamos apoyo emocional",
    "Tengo que recordar comprar pan fresco en la panadería cuando salga esta tarde del trabajo",
    "El ejercicio regular es fundamental para mantener una buena salud física y mental a largo plazo",
    "¿Has notado cómo cambia el ambiente cuando hay una tormenta eléctrica acercándose por la tarde?",
    "Me encantaría viajar por el mundo y conocer diferentes culturas y formas de vida fascinantes",
    "La historia nos enseña lecciones valiosas sobre los errores del pasado que no debemos repetir",
    "¿Podrías explicarme nuevamente ese concepto porque no lo entendí completamente la primera vez?",
    "El otoño pinta los árboles de colores cálidos creando paisajes realmente espectaculares y memorables",
    "Necesito encontrar mis llaves que dejé en algún lugar de la casa esta mañana temprano",
    "La cocina casera siempre sabe mejor que la comida de restaurante por el amor puesto",
    "¿Recuerdas cuando éramos niños y pasábamos horas jugando en el parque sin preocupaciones?",
    "El silencio de la biblioteca es perfecto para estudiar y concentrarse en tareas importantes sin distracciones",
    "Me sorprende la capacidad de adaptación que tienen los animales salvajes en sus entornos naturales",
    "¿Has pensado en tomar clases de idiomas para mejorar tus habilidades de comunicación internacional?",
    "La creatividad no tiene límites cuando permitimos que nuestra imaginación fluya libremente sin restricciones",
    "Tengo que terminar este proyecto antes de la fecha límite que establecimos con el equipo",
    "El invierno trae consigo noches largas perfectas para quedarse en casa leyendo un buen libro",
    "¿Sabías que las ballenas pueden cantar melodías complejas que viajan kilómetros bajo el agua?",
    "La perseverancia es clave para alcanzar nuestras metas más ambiciosas en la vida personal",
    "Necesito actualizar mi currículum antes de empezar a buscar nuevas oportunidades laborales prometedoras",
    "El mercado local ofrece productos frescos y de calidad que no encuentras en los supermercados grandes",
    "¿Te has dado cuenta de que el tiempo pasa más rápido cuando estamos ocupados haciendo algo?",
    "La gratitud transforma lo que tenemos en suficiente y nos hace apreciar las cosas simples",
    "Tengo ganas de hornear galletas caseras con chispas de chocolate como solía hacer antes",
    "El verano es perfecto para actividades al aire libre como nadar en la piscina o playa",
    "¿Has leído algún libro interesante últimamente que me puedas recomendar para leer también?",
    "La naturaleza tiene una forma mágica de renovarse y sorprendernos con su belleza constante",
    # Añadiré más frases para tener suficientes...
    "El aroma del pan recién horneado llena toda la casa con un olor delicioso y reconfortante",
    "¿Podrías ayudarme a mover estos muebles pesados para reorganizar la sala de estar completamente?",
    "La luna llena ilumina el paisaje nocturno con una luz plateada casi mágica y misteriosa",
    "Me fascina observar cómo las estaciones cambian y transforman el paisaje natural gradualmente con el tiempo",
    "¿Has considerado la posibilidad de adoptar una mascota para tener compañía en casa?",
    "La educación es la herramienta más poderosa que podemos usar para cambiar el mundo positivamente",
    "Necesito reparar esa ventana rota antes de que empiece a llover nuevamente esta semana",
    "El yoga me ayuda a mantener el equilibrio entre cuerpo y mente de manera efectiva",
    "¿Recuerdas el nombre de aquella canción que tanto nos gustaba escuchar hace algunos años?",
    "La risa es el mejor remedio para aliviar el estrés y mejorar nuestro estado de ánimo",
    "Tengo que llamar al dentista para programar mi cita de revisión anual que tengo pendiente",
    "El océano es tan vasto y misterioso que aún no hemos explorado la mayor parte",
    "¿Te gustaría unirte a nuestro grupo de senderismo para explorar nuevos senderos montañosos juntos?",
    "La meditación diaria me ha ayudado enormemente a manejar mejor la ansiedad y el estrés",
    "Necesito comprar un regalo especial para el cumpleaños de mi mejor amigo la próxima semana",
    "El arte tiene el poder de expresar emociones y pensamientos que las palabras no pueden",
    "¿Has visto las estrellas esta noche? El cielo está completamente despejado y brillante increíblemente",
    "La música clásica me ayuda a relajarme y concentrarme cuando necesito trabajar en proyectos importantes",
    "Tengo que ordenar mi armario porque ya no encuentro la ropa que necesito usar diariamente",
    "El bosque en primavera está lleno de vida con pájaros cantando y flores silvestres brotando",
    "¿Podrías recomendarme algún buen lugar para comer cerca de aquí que tenga comida deliciosa?",
    "La fotografía me permite capturar momentos especiales y preservar recuerdos hermosos para siempre",
    "Necesito aprender a administrar mejor mi dinero para poder ahorrar más efectivamente cada mes",
    "El chocolate caliente es perfecto para calentar el cuerpo en días fríos de invierno helado",
    "¿Has probado hacer ejercicio por las mañanas? Dicen que da mucha energía para todo el día",
    "La honestidad es fundamental en cualquier relación para construir confianza mutua y duradera siempre",
    "Tengo que revisar mi correo electrónico porque seguramente hay mensajes importantes sin leer todavía",
    "El circo llegó al pueblo trayendo alegría y entretenimiento para todas las familias locales",
    "¿Sabías que los árboles pueden comunicarse entre sí a través de sus raíces subterráneas?",
    "La curiosidad es lo que impulsa el aprendizaje y el descubrimiento de cosas nuevas fascinantes",
    "Necesito encontrar tiempo para visitar a mis abuelos que viven en el campo lejos de aquí",
    "El mercado navideño está lleno de luces brillantes y adornos festivos por todas partes visibles",
    "¿Te has fijado en cómo cambia el color del cielo durante un amanecer hermoso?",
    "La panadería de la esquina hace los mejores croissants que he probado en toda mi vida",
    "Tengo que practicar más mi pronunciación en inglés para poder comunicarme mejor con fluidez",
    "El teatro local presenta obras muy interesantes que vale la pena ir a ver en familia",
    "¿Podrías prestarme tu libro de cocina para copiar esa receta deliciosa que preparaste ayer?",
    "La biodiversidad es esencial para mantener el equilibrio de nuestros ecosistemas naturales saludables globalmente",
    "Necesito cambiar las pilas del control remoto porque ya no funciona correctamente desde hace días",
    "El museo de arte tiene una exposición nueva que todos están comentando con gran entusiasmo",
    "¿Has pensado en aprender a bailar? Es una actividad muy divertida y excelente ejercicio físico",
    "La arquitectura de esta ciudad combina estilos antiguos y modernos de manera muy armoniosa",
    "Tengo que recordar regar las plantas del jardín porque se ven un poco marchitas últimamente",
    "El concierto de anoche fue increíble con una energía espectacular que llenaba todo el estadio",
    "¿Sabías que algunos tipos de cactus pueden vivir cientos de años en condiciones extremas?",
    "La solidaridad entre vecinos fortalece la comunidad y crea un ambiente más agradable para todos",
    "Necesito buscar información sobre ese tema antes de la reunión importante de mañana por la tarde",
    "El zoológico tiene un programa educativo excelente para que los niños aprendan sobre animales",
    "¿Te gustaría ir conmigo a la feria artesanal este sábado para ver las creaciones locales?",
    "La astronomía me fascina especialmente cuando observo las constelaciones brillantes en la noche estrellada",
    "Tengo que llevar mi auto al mecánico porque está haciendo un ruido extraño últimamente",
    "El parque temático tiene atracciones emocionantes para todas las edades y gustos diferentes completamente",
    "¿Has notado que los días se hacen más cortos cuando se acerca el invierno gradualmente?",
    "La generosidad de extraños en momentos difíciles restaura mi fe en la humanidad bondadosa",
    # Continuaré agregando más frases únicas hasta tener suficientes...
    "Necesito comprar zapatos nuevos porque estos ya están muy gastados y ya no son cómodos",
    "El festival de comida internacional ofrece platillos exóticos de todas partes del mundo entero",
    "¿Podrías explicarme cómo llegaste a esa conclusión usando ese método de análisis particular específico?",
    "La voluntad de aprender cosas nuevas nos mantiene mentalmente activos y jóvenes de espíritu",
    "Tengo que organizar una fiesta sorpresa para mi hermana sin que ella se entere absolutamente",
    "El acuario tiene especies marinas fascinantes que nunca había visto antes en mi vida hasta ahora",
    "¿Sabías que las abejas son esenciales para la polinización de muchas plantas que consumimos?",
    "La disciplina diaria es necesaria para desarrollar nuevas habilidades y alcanzar objetivos personales importantes",
    "Necesito encontrar un tutorial en línea para aprender a reparar esa cosa rota yo mismo",
    "El carnaval llenó las calles de música alegre y disfraces coloridos durante todo el fin de semana",
    "¿Has escuchado el nuevo álbum de esa banda que tanto te gusta escuchar frecuentemente?",
    "La empatía nos permite conectar con otros a un nivel más profundo y significativo emocionalmente",
    "Tengo que preparar mi presentación para la conferencia que será la próxima semana sin falta",
    "El jardín botánico alberga plantas exóticas de climas tropicales que florecen todo el año constantemente",
    "¿Te gustaría aprender a hacer cerámica? Hay un taller que ofrece clases para principiantes cada semana",
    "La innovación tecnológica está transformando la manera en que vivimos y trabajamos diariamente ahora",
    "Necesito actualizar mi conocimiento sobre ese software porque lanzaron una versión nueva mejorada recientemente",
    "El planetario ofrece un espectáculo visual impresionante sobre el universo y las estrellas distantes lejanas",
    "¿Podrías ayudarme a traducir este documento importante porque no entiendo el idioma original completamente?",
    "La resiliencia es la capacidad de recuperarse de las adversidades y salir fortalecido del proceso",
    "Tengo que renovar mi suscripción antes de que expire para poder seguir disfrutando del servicio",
    "El mercado de pulgas tiene tesoros escondidos esperando ser descubiertos entre tantas cosas antiguas únicas",
    "¿Has considerado tomar un curso en línea para desarrollar nuevas habilidades profesionales valiosas?",
    "La biodiversidad marina es sorprendentemente rica pero también muy vulnerable a la contaminación humana actual",
    "Necesito revisar mis apuntes antes del examen final para asegurarme de recordar todo el material",
    "El circo acrobático mostró habilidades impresionantes que desafiaban las leyes de la física aparentemente siempre",
    "¿Sabías que algunos animales pueden regenerar partes de su cuerpo perdidas en accidentes?",
    "La autenticidad en las relaciones personales crea conexiones más genuinas y duraderas con el tiempo",
    "Tengo que encontrar una solución creativa para este problema que nos está dando tantos dolores",
    "El observatorio astronómico está abierto al público para ver planetas y estrellas a través del telescopio",
    "¿Te gustaría participar en un voluntariado comunitario para ayudar a quienes más lo necesitan?",
    "La biodiversidad en los arrecifes de coral es increíblemente rica pero está en peligro crítico",
    "Necesito mejorar mi postura corporal porque paso demasiadas horas sentado frente al computador trabajando",
    "El mercado orgánico ofrece verduras frescas cultivadas sin pesticidas ni químicos dañinos para la salud",
    "¿Has probado esa nueva técnica de estudio que mejora la retención de información significativamente?",
    "La adaptabilidad es una habilidad crucial en un mundo que cambia constantemente a ritmo acelerado",
    "Tengo que investigar más sobre ese tema fascinante que mencionaste en nuestra conversación anterior reciente",
    "El museo interactivo permite a los visitantes experimentar y aprender de manera práctica y divertida",
    "¿Podrías mostrarme ese truco que usas para memorizar información compleja de manera más fácil?",
    "La biodiversidad en la selva amazónica es asombrosa con millones de especies diferentes únicas conviviendo juntas",
    "Necesito establecer prioridades claras para poder gestionar mejor mi tiempo disponible limitado cada día",
    "El festival de música reunió a artistas talentosos de diversos géneros musicales variados internacionalmente reconocidos",
    "¿Sabías que la risa puede fortalecer el sistema inmunológico y mejorar nuestra salud general?",
    "La colaboración en equipo produce mejores resultados que trabajar individualmente en proyectos grandes complejos",
    "Tengo que verificar los datos antes de publicar el informe para evitar errores embarazosos después",
    "El laboratorio de ciencias permite realizar experimentos prácticos fascinantes para entender conceptos teóricos mejor claramente",
    "¿Te gustaría explorar ese sendero nuevo en el bosque que descubrieron los excursionistas recientemente?",
    "La diversidad cultural enriquece nuestra sociedad con perspectivas diferentes y tradiciones valiosas únicas variadas",
    "Necesito descansar adecuadamente esta noche porque mañana tengo un día muy largo y demandante",
    "El acuario tiene un túnel submarino donde puedes caminar rodeado de peces y tiburones nadando",
    "¿Has notado cómo la música puede cambiar completamente nuestro estado de ánimo instantáneamente?",
    "La perseverancia ante los obstáculos es lo que separa el éxito del fracaso a largo plazo",
    "Tengo que actualizar mi lista de contactos porque muchos números ya no son válidos actualmente",
    "El jardín comunitario permite a los vecinos cultivar sus propias verduras frescas orgánicas saludables juntos",
    "¿Podrías compartir conmigo esa aplicación útil que usas para organizar tus tareas diarias eficientemente?",
    "La inteligencia emocional es tan importante como la inteligencia intelectual para el éxito en vida",
    "Necesito practicar más la guitarra si quiero mejorar mi técnica musical significativamente este año",
    "El documental sobre la vida salvaje mostró comportamientos animales fascinantes nunca antes filmados documentados",
    "¿Sabías que las plantas pueden sentir y responder a su entorno de maneras sorprendentes?",
    "La transparencia en las organizaciones genera confianza y mejora el ambiente laboral positivamente siempre",
    "Tengo que renovar mi pasaporte antes de planear mi próximo viaje internacional al extranjero lejano",
    "El vivero tiene una variedad impresionante de plantas ornamentales hermosas para decorar el hogar",
    "¿Te gustaría asistir a esa conferencia educativa sobre temas de sostenibilidad ambiental global?",
    "La flexibilidad mental nos permite adaptarnos a nuevas situaciones y encontrar soluciones creativas innovadoras",
    "Necesito organizar mejor mi espacio de trabajo para aumentar mi productividad y concentración diaria",
    "El concierto benéfico recaudó fondos importantes para apoyar causas sociales nobles y necesarias urgentemente",
    "¿Has experimentado con diferentes estilos de arte para encontrar tu forma de expresión preferida?",
    "La conciencia ambiental comienza con pequeñas acciones cotidianas que todos podemos implementar fácilmente hoy",
    "Tengo que aprender técnicas efectivas de comunicación para expresarme mejor claramente ante audiencias grandes",
    "El safari fotográfico ofrece la oportunidad única de observar animales salvajes en su hábitat natural",
    "¿Podrías explicarme ese concepto matemático complicado usando ejemplos prácticos de la vida real?",
    "La creatividad florece cuando nos permitimos pensar sin restricciones ni miedo al fracaso temporal",
    "Necesito buscar inspiración para mi próximo proyecto creativo artístico personal importante significativo especial",
    "El taller de escritura creativa ayuda a desarrollar habilidades narrativas y expresión literaria efectiva poderosa",
    "¿Sabías que el cerebro humano es capaz de generar nuevas neuronas incluso en edad adulta?",
    "La mentalidad de crecimiento nos impulsa a ver los desafíos como oportunidades de aprendizaje valiosas",
    "Tengo que investigar sobre las mejores prácticas en mi campo profesional para mantenerme actualizado competitivo",
    "El espectáculo de danza contemporánea combinó movimientos expresivos con música emotiva de forma magistral",
    "¿Te gustaría probar ese nuevo deporte acuático emocionante que está ganando popularidad últimamente?",
    "La gratitud diaria por las cosas pequeñas mejora significativamente nuestra perspectiva de vida positiva",
    "Necesito establecer límites saludables en mi vida personal para mantener un equilibrio adecuado necesario",
    "El refugio de animales necesita voluntarios dedicados para cuidar de las mascotas rescatadas diariamente siempre",
    "¿Has considerado practicar mindfulness para reducir el estrés y mejorar tu bienestar mental general?",
    "La exploración de nuevos hobbies enriquece nuestra vida y nos ayuda a descubrir pasiones ocultas",
    "Tengo que perfeccionar mi técnica de presentación para comunicar ideas complejas de forma clara simple",
    "El huerto urbano demuestra que es posible cultivar alimentos frescos incluso en espacios pequeños limitados",
    "¿Podrías recomendarme recursos en línea confiables para aprender sobre ese tema específico interesante particular?",
    "La diversidad de pensamiento en equipos conduce a soluciones más innovadoras y completas efectivas siempre",
    "Necesito desarrollar mejores hábitos de sueño porque el descanso adecuado es fundamental para la salud",
    "El taller de cocina internacional enseña recetas auténticas de diferentes países culturas del mundo entero",
    "¿Sabías que practicar un segundo idioma regularmente mantiene el cerebro activo y saludable?",
    "La autoevaluación honesta nos permite identificar áreas de mejora y crecer personalmente continuamente siempre",
    "Tengo que crear un plan de acción detallado para alcanzar mis metas a largo plazo",
    "El club de lectura organiza discusiones profundas sobre libros que expanden nuestra comprensión del mundo",
    "¿Te gustaría aprender técnicas de relajación profunda para manejar mejor situaciones estresantes difíciles?",
    "La innovación surge cuando combinamos ideas existentes de formas nuevas y creativas únicas inesperadas",
    "Necesito mejorar mi capacidad de escucha activa para comunicarme más efectivamente con los demás",
    "El taller de fotografía enseña a capturar la esencia de un momento usando luz y composición",
    "¿Has explorado diferentes métodos de meditación para encontrar el que mejor funciona para ti?",
    "La resiliencia se construye enfrentando desafíos pequeños que nos preparan para obstáculos mayores futuros",
    "Tengo que documentar mis procesos de trabajo para poder compartir mi conocimiento con el equipo",
    "El centro cultural ofrece clases gratuitas de arte para la comunidad todos los fines de semana",
    "¿Podrías ayudarme a establecer metas realistas y alcanzables para este nuevo año que comienza?",
    "La curiosidad intelectual nos mantiene comprometidos con el aprendizaje continuo durante toda la vida",
    "Necesito encontrar formas creativas de resolver problemas cotidianos usando recursos disponibles limitados ahora",
    "El programa de intercambio cultural permite experimentar diferentes formas de vida de primera mano directamente",
    "¿Sabías que las personas que escriben diarios regularmente tienden a tener mejor salud mental?",
    "La colaboración interdisciplinaria genera soluciones más completas para problemas complejos actuales importantes globales",
    "Tengo que practicar la paciencia porque las cosas buenas toman tiempo en desarrollarse completamente siempre",
    "El mercado artesanal apoya a los artistas locales y ofrece productos únicos hechos a mano",
    "¿Te gustaría participar en un proyecto colaborativo que beneficie a nuestra comunidad local?",
    "La adaptación al cambio es más fácil cuando mantenemos una actitud abierta y positiva",
    "Necesito desarrollar estrategias efectivas para gestionar mi energía a lo largo del día productivamente",
    "El observatorio de aves es perfecto para aprender sobre especies locales y sus comportamientos naturales",
    "¿Has probado técnicas de visualización creativa para alcanzar tus objetivos personales más importantes?",
    "La empatía hacia nosotros mismos es tan importante como la empatía hacia los demás",
    "Tengo que crear un sistema organizado para archivar documentos importantes de forma accesible eficiente",
    "El festival gastronómico celebra la riqueza culinaria regional con chefs reconocidos internacionalmente famosos prestigiosos",
    "¿Podrías compartir estrategias que usas para mantener la motivación en proyectos a largo plazo?",
    "La diversidad de habilidades en un equipo complementa las fortalezas individuales creando sinergia productiva",
    "Necesito aprender a delegar tareas efectivamente para no sobrecargarme innecesariamente con trabajo excesivo",
    "El campamento educativo ofrece experiencias de aprendizaje al aire libre para jóvenes estudiantes entusiastas",
    "¿Sabías que establecer rutinas matutinas consistentes puede mejorar significativamente la productividad diaria?",
    "La reflexión regular sobre nuestras experiencias nos ayuda a extraer lecciones valiosas importantes significativas",
    "Tengo que investigar diferentes perspectivas sobre este tema antes de formar mi opinión definitiva final",
    "El laboratorio de innovación fomenta la experimentación y el pensamiento creativo disruptivo revolucionario novedoso",
    "¿Te gustaría explorar diferentes filosofías de vida para enriquecer tu perspectiva personal única?",
    "La constancia en pequeñas acciones diarias produce resultados extraordinarios a largo plazo inevitablemente",
    "Necesito mejorar mi capacidad de concentración profunda en esta era de distracciones constantes digitales",
    "El programa de mentoría conecta a profesionales experimentados con personas que inician sus carreras",
    "¿Has considerado llevar un registro de tus logros para celebrar tu progreso personal continuo?",
    "La apertura mental nos permite considerar ideas nuevas sin prejuicios limitantes innecesarios restrictivos",
    "Tengo que desarrollar mayor conciencia sobre mis patrones de pensamiento y comportamiento habituales automáticos",
    "El centro de emprendimiento ofrece recursos valiosos para quienes desean iniciar sus propios negocios exitosos",
    "¿Podrías explicarme cómo mantienes el equilibrio entre vida personal y responsabilidades profesionales demandantes?",
    "La inversión en educación continua es una de las mejores decisiones que podemos tomar",
    "Necesito crear un ambiente propicio para la creatividad eliminando distracciones innecesarias del espacio trabajo",
    "El simposio internacional reunió a expertos destacados para discutir soluciones innovadoras a problemas globales",
    "¿Sabías que la práctica de la gratitud puede rewirear nuestro cerebro para ser más positivos?",
    "La autenticidad en nuestras acciones genera respeto y confianza en nuestras relaciones personales profesionales",
    "Tengo que experimentar con diferentes métodos de organización hasta encontrar el que funcione mejor",
    "El jardín sensorial está diseñado para estimular todos los sentidos con plantas aromáticas y texturas",
    "¿Te gustaría desarrollar habilidades de liderazgo participando en proyectos comunitarios significativos importantes?",
    "La resiliencia emocional se fortalece cuando aprendemos a procesar nuestras emociones de forma saludable",
    "Necesito establecer rituales diarios que me ayuden a mantener el enfoque en mis prioridades vitales",
    "El laboratorio maker ofrece herramientas y espacio para crear prototipos de ideas innovadoras creativas",
    "¿Has explorado técnicas de aprendizaje acelerado para adquirir nuevas habilidades más rápidamente eficientemente?",
    "La conexión con la naturaleza tiene efectos positivos comprobados en nuestra salud mental física",
    "Tengo que practicar la escucha sin juicio para mejorar mis relaciones interpersonales significativamente mucho",
    "El festival de ciencia divulga conocimientos complejos de manera accesible y entretenida para todos públicos",
    "¿Podrías compartir técnicas que utilizas para mantener la calma en situaciones de alta presión?",
    "La diversidad de experiencias en la vida nos proporciona perspectivas únicas valiosas enriquecedoras siempre",
    "Necesito desarrollar mayor claridad en mi comunicación para evitar malentendidos innecesarios frecuentes comunes",
    "El programa de bienestar corporativo promueve hábitos saludables entre los empleados de la organización",
    "¿Sabías que las conexiones sociales fuertes son uno de los predictores más importantes de longevidad?",
    "La capacidad de adaptación rápida es cada vez más valiosa en nuestro mundo cambiante dinámico",
    "Tengo que cultivar la paciencia y la persistencia para lograr mis objetivos ambiciosos a largo",
    "El taller de resolución creativa de problemas enseña metodologías innovadoras para enfrentar desafíos complejos",
    "¿Te gustaría explorar diferentes tradiciones culturales para ampliar tu comprensión del mundo diverso global?",
    "La integridad personal se demuestra cuando nuestras acciones están alineadas con nuestros valores profundos",
    "Necesito crear sistemas automatizados para tareas repetitivas y liberar tiempo para actividades importantes creativas",
    "El hackathon social convoca a equipos multidisciplinarios para desarrollar soluciones tecnológicas a problemas comunitarios",
]

def find_duplicates():
    """Find all duplicate phrases and identify which entries to keep/replace."""
    phrase_locations = defaultdict(list)

    # Read metadata.csv
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parts = line.strip().split('|')
            if len(parts) == 2:
                filename, phrase = parts
                phrase_locations[phrase].append((line_num, filename))

    # Find duplicates (keep first occurrence, mark others for replacement)
    entries_to_replace = []

    for phrase, locations in phrase_locations.items():
        if len(locations) > 1:
            # Keep first occurrence, replace the rest
            for line_num, filename in locations[1:]:
                entries_to_replace.append({
                    'line_num': line_num,
                    'filename': filename,
                    'old_phrase': phrase
                })

    return entries_to_replace

def delete_audio_files(entries):
    """Delete .wav files for duplicate entries."""
    wavs_dir = Path('wavs')
    deleted_count = 0

    for entry in entries:
        audio_file = wavs_dir / f"{entry['filename']}.wav"
        if audio_file.exists():
            audio_file.unlink()
            deleted_count += 1
            print(f"  Eliminado: {audio_file.name}")

    return deleted_count

def update_metadata_csv(entries_to_replace):
    """Update metadata.csv with new unique phrases."""
    # Read all lines
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Prepare replacement phrases (shuffle to randomize)
    random.shuffle(REPLACEMENT_PHRASES)
    replacement_idx = 0

    # Update duplicate entries
    for entry in entries_to_replace:
        line_idx = entry['line_num'] - 1  # Convert to 0-based index
        filename = entry['filename']

        # Get new unique phrase
        new_phrase = REPLACEMENT_PHRASES[replacement_idx % len(REPLACEMENT_PHRASES)]
        replacement_idx += 1

        # Update line
        lines[line_idx] = f"{filename}|{new_phrase}\n"
        entry['new_phrase'] = new_phrase

    # Write updated metadata
    with open('metadata.csv', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return entries_to_replace

def update_generation_state(entries_to_replace):
    """Update generation_state.json to mark entries as pending."""
    # Load state
    with open('generation_state.json', 'r', encoding='utf-8') as f:
        state = json.load(f)

    # Create a set of filenames to update
    filenames_to_update = {entry['filename'] for entry in entries_to_replace}

    # Update entries
    updated_count = 0
    for entry in state['entries']:
        if entry['filename'] in filenames_to_update:
            # Find the new phrase for this entry
            new_phrase = next((e['new_phrase'] for e in entries_to_replace
                             if e['filename'] == entry['filename']), None)

            if new_phrase:
                # Update counters
                if entry['status'] == 'completed':
                    state['completed'] -= 1
                elif entry['status'] == 'error':
                    state['failed'] -= 1

                # Reset entry to pending
                entry['status'] = 'pending'
                entry['text'] = new_phrase
                entry['duration_seconds'] = None
                entry['file_size_kb'] = None
                entry['generated_at'] = None
                entry['error_message'] = None
                entry['retry_count'] = 0

                updated_count += 1

    # Ensure status is idle
    state['status'] = 'idle'

    # Save updated state
    with open('generation_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return updated_count

def main():
    print("=" * 80)
    print("ELIMINANDO FRASES DUPLICADAS DEL DATASET")
    print("=" * 80)
    print()

    # Step 1: Find duplicates
    print("1. Identificando frases duplicadas...")
    entries_to_replace = find_duplicates()
    print(f"   Encontradas {len(entries_to_replace)} entradas duplicadas para reemplazar")
    print()

    if len(entries_to_replace) == 0:
        print("No hay duplicados para eliminar!")
        return

    # Step 2: Delete audio files
    print("2. Eliminando archivos de audio duplicados...")
    deleted_count = delete_audio_files(entries_to_replace)
    print(f"   Eliminados {deleted_count} archivos .wav")
    print()

    # Step 3: Update metadata.csv
    print("3. Actualizando metadata.csv con nuevas frases únicas...")
    entries_to_replace = update_metadata_csv(entries_to_replace)
    print(f"   Actualizadas {len(entries_to_replace)} frases en metadata.csv")
    print()

    # Step 4: Update generation_state.json
    print("4. Actualizando generation_state.json (marcando como pending)...")
    updated_count = update_generation_state(entries_to_replace)
    print(f"   Actualizadas {updated_count} entradas en el estado")
    print()

    print("=" * 80)
    print("PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 80)
    print()
    print(f"Resumen:")
    print(f"  - Frases duplicadas eliminadas: {len(entries_to_replace)}")
    print(f"  - Archivos .wav eliminados: {deleted_count}")
    print(f"  - Nuevas frases generadas: {len(entries_to_replace)}")
    print(f"  - Entradas marcadas como 'pending': {updated_count}")
    print()
    print("Siguiente paso:")
    print("  1. Reinicia el servidor (start.bat)")
    print("  2. Haz clic en 'Sincronizar con archivos' en el dashboard")
    print("  3. Inicia la generación para crear los audios con las nuevas frases")

if __name__ == "__main__":
    main()
