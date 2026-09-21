"""Seed content: natural British English phrases with listening notes (Romanian)."""

PHRASES: list[dict] = [
    # ------------------------------------------------------------------ everyday
    {
        "text": "Would you like me to pick you up after work?",
        "translation_ro": "Vrei să te iau (cu mașina) după muncă?",
        "topic": "everyday",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "Would you",
                "sounds_like": "/wʊdʒu/",
                "explanation_ro": "„d” + „y” se contopesc într-un sunet „ge” (/dʒ/): „would you” sună aproape ca un singur cuvânt.",
            },
            {
                "pattern": "weak-form",
                "fragment": "to",
                "sounds_like": "/tə/",
                "explanation_ro": "„to” e neaccentuat și devine /tə/, un sunet scurt și slab.",
            },
            {
                "pattern": "linking",
                "fragment": "pick you up",
                "sounds_like": "",
                "explanation_ro": "Consoana de la finalul unui cuvânt se leagă de vocala următoare: „pick you‿up”.",
            },
        ],
    },
    {
        "text": "I'll sort it out later.",
        "translation_ro": "Rezolv mai târziu.",
        "topic": "everyday",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "I'll",
                "sounds_like": "/aɪl/",
                "explanation_ro": "„I will” se scurtează la „I'll”, iar „l”-ul final abia se aude, așa că pare doar „I”.",
            },
            {
                "pattern": "linking",
                "fragment": "sort it out",
                "sounds_like": "",
                "explanation_ro": "Cele trei cuvinte curg împreună („sor-ti-tout”), fără pauze, și e greu să vezi unde începe fiecare.",
            },
        ],
    },
    {
        "text": "I might pop in on the way home.",
        "translation_ro": "S-ar putea să trec pe acolo în drum spre casă.",
        "topic": "everyday",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "might",
                "sounds_like": "/maɪʔ/",
                "explanation_ro": "Înainte de o consoană, „t”-ul din „might” devine o scurtă oprire în gât, deci auzi doar „mai-”.",
            },
            {
                "pattern": "linking",
                "fragment": "pop in on",
                "sounds_like": "",
                "explanation_ro": "„p” și „n” se leagă de vocalele următoare: „po‿pi‿non” sună ca un singur cuvânt.",
            },
        ],
    },
    {
        "text": "Can you put the kettle on?",
        "translation_ro": "Poți să pui de-un ceai (să fierbi apa)?",
        "topic": "everyday",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Can",
                "sounds_like": "/kən/",
                "explanation_ro": "În întrebări, „can” e neaccentuat și devine /kən/, aproape doar „k'n”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "put the",
                "sounds_like": "/pʊʔ ðə/",
                "explanation_ro": "„t”-ul din „put” e înlocuit de o oprire în gât înainte de „the”, deci pare „pu' the”.",
            },
        ],
    },
    {
        "text": "I'm just going to nip to the shop.",
        "translation_ro": "Dau o fugă până la magazin.",
        "topic": "everyday",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "elision",
                "fragment": "just",
                "sounds_like": "/dʒʌs/",
                "explanation_ro": "„t”-ul din „just” dispare înaintea altei consoane, deci auzi doar „jus”.",
            },
            {
                "pattern": "everyday-reduction",
                "fragment": "going to",
                "sounds_like": "gonna",
                "explanation_ro": "„going to” (pentru viitor) se reduce la „gonna” în vorbirea obișnuită.",
            },
        ],
    },
    {
        "text": "Could you turn the telly down a bit?",
        "translation_ro": "Poți să dai televizorul puțin mai încet?",
        "topic": "everyday",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "Could you",
                "sounds_like": "/kʊdʒu/",
                "explanation_ro": "„d” + „y” se unesc în /dʒ/, deci „could you” sună ca „cugiu”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "a bit",
                "sounds_like": "/ə bɪʔ/",
                "explanation_ro": "„t”-ul final din „bit” e adesea doar o oprire în gât, așa că pare „a bi'”.",
            },
        ],
    },
    {
        "text": "Just leave them by the door, I'll deal with them later.",
        "translation_ro": "Lasă-le lângă ușă, mă ocup de ele mai târziu.",
        "topic": "everyday",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "them",
                "sounds_like": "/ðəm/",
                "explanation_ro": "„them” neaccentuat devine /ðəm/ sau chiar /əm/, ușor de confundat cu „'em”.",
            },
            {
                "pattern": "contraction",
                "fragment": "I'll",
                "sounds_like": "/aɪl/",
                "explanation_ro": "„I'll” se lipește de verb și „l”-ul se pierde ușor în vorbirea rapidă.",
            },
        ],
    },
    # ---------------------------------------------------------------------- work
    {
        "text": "Did you get a chance to look at it?",
        "translation_ro": "Ai apucat să te uiți pe el?",
        "topic": "work",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "Did you",
                "sounds_like": "/dɪdʒu/",
                "explanation_ro": "„d” + „y” devin /dʒ/: „did you” sună ca „digiu”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "get a",
                "sounds_like": "/ɡeʔ ə/",
                "explanation_ro": "„t”-ul din „get” e înlocuit de o oprire în gât, iar „a” se lipește: „ge'a”.",
            },
            {
                "pattern": "linking",
                "fragment": "look at it",
                "sounds_like": "",
                "explanation_ro": "„look‿at‿it” se leagă într-un singur bloc, cu „at” redus la /ət/.",
            },
        ],
    },
    {
        "text": "Have you got a minute?",
        "translation_ro": "Ai un minut?",
        "topic": "work",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Have you",
                "sounds_like": "/həv jə/",
                "explanation_ro": "La început de întrebare, „have” e slab (/həv/, uneori /əv/), iar „you” devine /jə/.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "got a",
                "sounds_like": "/ɡɒʔ ə/",
                "explanation_ro": "„t”-ul din „got” devine o oprire în gât: „go'a”, foarte tipic în Marea Britanie.",
            },
        ],
    },
    {
        "text": "Can we push the meeting back to Thursday?",
        "translation_ro": "Putem amâna ședința pe joi?",
        "topic": "work",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Can",
                "sounds_like": "/kən/",
                "explanation_ro": "„can” neaccentuat se reduce la /kən/, deci se aude mai mult „k'n we”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "to",
                "sounds_like": "/tə/",
                "explanation_ro": "„to” devine /tə/ și se pierde între „back” și „Thursday”.",
            },
        ],
    },
    {
        "text": "I'll send it over first thing tomorrow.",
        "translation_ro": "Ți-l trimit mâine la prima oră.",
        "topic": "work",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "linking",
                "fragment": "send it over",
                "sounds_like": "",
                "explanation_ro": "„send‿it‿over” curge legat, „it” fiind abia un „i” scurt între consoane.",
            },
            {
                "pattern": "elision",
                "fragment": "first thing",
                "sounds_like": "/fɜːs θɪŋ/",
                "explanation_ro": "„t”-ul din „first” dispare înainte de „th”, deci auzi „firs' thing”.",
            },
        ],
    },
    {
        "text": "Sorry, I'm running a bit late this morning.",
        "translation_ro": "Scuze, am o mică întârziere în dimineața asta.",
        "topic": "work",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "linking",
                "fragment": "running a",
                "sounds_like": "",
                "explanation_ro": "„a” se lipește de „running”, deci pare un singur cuvânt: „runninga”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "bit late",
                "sounds_like": "/bɪʔ leɪt/",
                "explanation_ro": "„t”-ul din „bit” devine oprire în gât înainte de „l”, așa că pare „bi' late”.",
            },
        ],
    },
    {
        "text": "Could you cover my shift on Saturday?",
        "translation_ro": "Poți să-mi acoperi tura de sâmbătă?",
        "topic": "work",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "Could you",
                "sounds_like": "/kʊdʒu/",
                "explanation_ro": "„d” + „y” se contopesc în /dʒ/, deci auzi „cugiu” în loc de două cuvinte.",
            },
            {
                "pattern": "schwa",
                "fragment": "Saturday",
                "sounds_like": "/ˈsætədeɪ/",
                "explanation_ro": "Silaba din mijloc e un schwa scurt /ə/, nu „ur”, deci cuvântul pare „Sat-ə-dei”.",
            },
        ],
    },
    {
        "text": "We should have finished it by now.",
        "translation_ro": "Ar fi trebuit să-l fi terminat până acum.",
        "topic": "work",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "should have",
                "sounds_like": "/ʃʊdəv/",
                "explanation_ro": "„have” după „should” devine doar /əv/, deci pare „shoulda” – de aici greșeala „should of”.",
            },
            {
                "pattern": "linking",
                "fragment": "finished it",
                "sounds_like": "",
                "explanation_ro": "Terminația „-ed” se pronunță /t/ și se leagă de „it”: „finish‿tit”, fără pauză.",
            },
        ],
    },
    # ------------------------------------------------------------------ shopping
    {
        "text": "Do you need a bag?",
        "translation_ro": "Aveți nevoie de o pungă?",
        "topic": "shopping",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "everyday-reduction",
                "fragment": "Do you",
                "sounds_like": "d'you",
                "explanation_ro": "La casă, „do you” se reduce la „d'you” (/djə/), aproape o singură silabă.",
            },
            {
                "pattern": "linking",
                "fragment": "need a",
                "sounds_like": "",
                "explanation_ro": "„d”-ul se leagă de „a”: „nee‿da bag”.",
            },
        ],
    },
    {
        "text": "That's ten pounds fifty, please.",
        "translation_ro": "Face zece lire și cincizeci, vă rog.",
        "topic": "shopping",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "ten pounds",
                "sounds_like": "/tem paʊndz/",
                "explanation_ro": "„n” devine „m” înainte de „p”, deci „ten pounds” sună ca „tem pounds”.",
            },
            {
                "pattern": "contraction",
                "fragment": "That's",
                "sounds_like": "/ðæts/",
                "explanation_ro": "„That is” devine „that's”, iar „s”-ul final se lipește de cuvântul următor.",
            },
        ],
    },
    {
        "text": "Can I pay by card?",
        "translation_ro": "Pot plăti cu cardul?",
        "topic": "shopping",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Can",
                "sounds_like": "/kən/",
                "explanation_ro": "„can” e slab (/kən/) și se leagă de „I”: „k'nai pay”.",
            },
        ],
    },
    {
        "text": "Have you got this in a smaller size?",
        "translation_ro": "Aveți asta și într-o mărime mai mică?",
        "topic": "shopping",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "got this",
                "sounds_like": "/ɡɒʔ ðɪs/",
                "explanation_ro": "„t”-ul din „got” se transformă în oprire în gât înainte de „this”: „go' this”.",
            },
            {
                "pattern": "linking",
                "fragment": "in a",
                "sounds_like": "",
                "explanation_ro": "„in‿a” se aude ca „ina”, un singur sunet scurt.",
            },
        ],
    },
    {
        "text": "Are you after anything in particular?",
        "translation_ro": "Căutați ceva anume?",
        "topic": "shopping",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "reduced-function-word",
                "fragment": "Are you",
                "sounds_like": "/ə jə/",
                "explanation_ro": "„are you” la început de întrebare e foarte slab (/ə jə/), aproape înghițit.",
            },
            {
                "pattern": "linking-r",
                "fragment": "after anything",
                "sounds_like": "/ɑːftər ˈeniθɪŋ/",
                "explanation_ro": "„r”-ul din „after”, de obicei mut, reapare înaintea vocalei: „afte‿r‿anything”.",
            },
            {
                "pattern": "schwa",
                "fragment": "particular",
                "sounds_like": "/pəˈtɪkjələ/",
                "explanation_ro": "Doar „ti” e accentuat; restul silabelor devin schwa, deci pare „pə-TI-kiu-lə”.",
            },
        ],
    },
    {
        "text": "Do you want a receipt?",
        "translation_ro": "Doriți bonul?",
        "topic": "shopping",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "everyday-reduction",
                "fragment": "Do you want a",
                "sounds_like": "d'you wanna",
                "explanation_ro": "Tot începutul se comprimă în „d'you wanna”, iar „receipt” e singurul cuvânt clar.",
            },
        ],
    },
    # --------------------------------------------------------------- phone-calls
    {
        "text": "I was going to give you a ring later.",
        "translation_ro": "Voiam să-ți dau un telefon mai târziu.",
        "topic": "phone-calls",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "was",
                "sounds_like": "/wəz/",
                "explanation_ro": "„was” neaccentuat devine /wəz/, un sunet scurt ușor de ratat.",
            },
            {
                "pattern": "everyday-reduction",
                "fragment": "going to",
                "sounds_like": "gonna",
                "explanation_ro": "„was going to” devine „was gonna”, adică „aveam de gând să”.",
            },
            {
                "pattern": "linking",
                "fragment": "give you a",
                "sounds_like": "",
                "explanation_ro": "„give you a” curge legat („givyuə”), cu „you” și „a” foarte slabe.",
            },
        ],
    },
    {
        "text": "Can I just take your name, please?",
        "translation_ro": "Îmi puteți spune numele, vă rog?",
        "topic": "phone-calls",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "elision",
                "fragment": "just take",
                "sounds_like": "/dʒʌs teɪk/",
                "explanation_ro": "Cele două „t” se reduc la unul, deci „just take” sună ca „jus' take”.",
            },
            {
                "pattern": "reduced-function-word",
                "fragment": "your",
                "sounds_like": "/jə/",
                "explanation_ro": "„your” neaccentuat devine /jə/, ușor de confundat cu „you” sau „a”.",
            },
        ],
    },
    {
        "text": "Sorry, you're breaking up a bit.",
        "translation_ro": "Scuze, nu te aud bine (se întrerupe).",
        "topic": "phone-calls",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "you're",
                "sounds_like": "/jɔː/",
                "explanation_ro": "„you are” devine „you're”, care sună ca „yor” sau chiar /jə/ – identic cu „your”.",
            },
            {
                "pattern": "linking",
                "fragment": "breaking up a",
                "sounds_like": "",
                "explanation_ro": "„breaking‿up‿a” se leagă: „brekin-gu-pə”, fără granițe clare între cuvinte.",
            },
        ],
    },
    {
        "text": "Could I speak to someone about my bill?",
        "translation_ro": "Aș putea vorbi cu cineva despre factura mea?",
        "topic": "phone-calls",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "to",
                "sounds_like": "/tə/",
                "explanation_ro": "„to” devine /tə/ și se lipește de „someone”.",
            },
            {
                "pattern": "linking",
                "fragment": "someone about",
                "sounds_like": "",
                "explanation_ro": "„n”-ul se leagă de vocala din „about”: „someo‿nabout”.",
            },
        ],
    },
    {
        "text": "I'm afraid she's not in at the moment.",
        "translation_ro": "Din păcate nu e aici momentan.",
        "topic": "phone-calls",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "she's",
                "sounds_like": "/ʃiːz/",
                "explanation_ro": "„she is” devine „she's” și se leagă de „not”, deci auzi „shiz not”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "at",
                "sounds_like": "/ət/",
                "explanation_ro": "„at” devine /ət/, aproape invizibil între „in” și „the moment”.",
            },
        ],
    },
    {
        "text": "Can you hold on for a second?",
        "translation_ro": "Puteți să așteptați o secundă?",
        "topic": "phone-calls",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "linking",
                "fragment": "hold on",
                "sounds_like": "",
                "explanation_ro": "„d”-ul se leagă de „on”: „hol‿don”.",
            },
            {
                "pattern": "linking-r",
                "fragment": "for a",
                "sounds_like": "/fər ə/",
                "explanation_ro": "„r”-ul din „for” se aude doar pentru că urmează o vocală: „fo‿ra second”.",
            },
        ],
    },
    {
        "text": "I'll get back to you as soon as I can.",
        "translation_ro": "Revin cu un răspuns cât de repede pot.",
        "topic": "phone-calls",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "get back",
                "sounds_like": "/ɡeʔ bæk/",
                "explanation_ro": "„t”-ul din „get” devine oprire în gât înainte de „b”: „ge' back”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "as soon as",
                "sounds_like": "/əz suːn əz/",
                "explanation_ro": "Ambele „as” devin /əz/, deci auzi clar doar „soon”.",
            },
        ],
    },
    {
        "text": "Can you tell him I called?",
        "translation_ro": "Poți să-i spui că am sunat?",
        "topic": "phone-calls",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "dropped-consonant",
                "fragment": "him",
                "sounds_like": "/ɪm/",
                "explanation_ro": "„h”-ul din „him” neaccentuat cade, iar „tell him” sună ca „tellim”.",
            },
        ],
    },
    # ----------------------------------------------------------------- transport
    {
        "text": "Mind the gap.",
        "translation_ro": "Atenție la spațiul dintre peron și tren.",
        "topic": "transport",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "elision",
                "fragment": "Mind the",
                "sounds_like": "/maɪn ðə/",
                "explanation_ro": "„d”-ul din „mind” dispare înainte de „the”, deci auzi „main' the gap”.",
            },
        ],
    },
    {
        "text": "Does this bus go to the station?",
        "translation_ro": "Autobuzul ăsta merge la gară?",
        "topic": "transport",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Does",
                "sounds_like": "/dəz/",
                "explanation_ro": "„does” la început de întrebare devine /dəz/, un sunet foarte scurt.",
            },
            {
                "pattern": "weak-form",
                "fragment": "to",
                "sounds_like": "/tə/",
                "explanation_ro": "„to” devine /tə/ și aproape dispare înainte de „the station”.",
            },
        ],
    },
    {
        "text": "The next train is delayed by ten minutes.",
        "translation_ro": "Următorul tren are o întârziere de zece minute.",
        "topic": "transport",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "elision",
                "fragment": "next train",
                "sounds_like": "/neks treɪn/",
                "explanation_ro": "„t”-ul din „next” dispare între „s” și „t”, deci auzi „nex' train”.",
            },
            {
                "pattern": "assimilation",
                "fragment": "ten minutes",
                "sounds_like": "/tem ˈmɪnɪts/",
                "explanation_ro": "„n” devine „m” înainte de alt „m”, deci pare „te-minutes”.",
            },
        ],
    },
    {
        "text": "Is this the right stop for the hospital?",
        "translation_ro": "Asta e stația bună pentru spital?",
        "topic": "transport",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "right stop",
                "sounds_like": "/raɪʔ stɒp/",
                "explanation_ro": "„t”-ul din „right” devine oprire în gât înainte de „s”: „rai' stop”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "for",
                "sounds_like": "/fə/",
                "explanation_ro": "„for” neaccentuat devine /fə/, ușor de confundat cu „a” sau „to”.",
            },
        ],
    },
    {
        "text": "Are you getting off at the next stop?",
        "translation_ro": "Coborâți la stația următoare?",
        "topic": "transport",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "reduced-function-word",
                "fragment": "Are you",
                "sounds_like": "/ə jə/",
                "explanation_ro": "„are you” e aproape înghițit: auzi mai ales „getting off”.",
            },
            {
                "pattern": "linking",
                "fragment": "getting off at",
                "sounds_like": "",
                "explanation_ro": "„getting‿off‿at” se leagă într-un bloc, cu „at” redus la /ət/.",
            },
            {
                "pattern": "elision",
                "fragment": "next stop",
                "sounds_like": "/neks stɒp/",
                "explanation_ro": "„t”-ul din „next” cade între două „s”, deci pare „nex' stop”.",
            },
        ],
    },
    {
        "text": "Stand clear of the closing doors, please.",
        "translation_ro": "Îndepărtați-vă de ușile care se închid, vă rog.",
        "topic": "transport",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "linking-r",
                "fragment": "clear of",
                "sounds_like": "/klɪər əv/",
                "explanation_ro": "„r”-ul din „clear” se aude doar pentru că urmează „of”: „clea‿rof”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "of",
                "sounds_like": "/əv/",
                "explanation_ro": "„of” devine /əv/, un sunet scurt lipit de cuvântul dinainte.",
            },
        ],
    },
    {
        "text": "Where are you off to?",
        "translation_ro": "Unde mergi?",
        "topic": "transport",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "linking-r",
                "fragment": "Where are",
                "sounds_like": "/weər ə/",
                "explanation_ro": "„r”-ul din „where” reapare înainte de „are”, iar „are” devine /ə/: „wea‿rə”.",
            },
            {
                "pattern": "linking",
                "fragment": "you off",
                "sounds_like": "",
                "explanation_ro": "„you‿off” se leagă printr-un „w” scurt: „yu‿woff”.",
            },
        ],
    },
    {
        "text": "Is it far away from the station?",
        "translation_ro": "E departe de gară?",
        "topic": "transport",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "linking-r",
                "fragment": "far away",
                "sounds_like": "/fɑːr əˈweɪ/",
                "explanation_ro": "„r”-ul din „far”, altfel mut, se aude înainte de „away”: „fa‿raway”.",
            },
            {
                "pattern": "linking",
                "fragment": "Is it",
                "sounds_like": "",
                "explanation_ro": "„Is‿it” se leagă într-un singur sunet scurt, „izit”.",
            },
        ],
    },
    # ---------------------------------------------------------------- healthcare
    {
        "text": "I'd like to book an appointment with a GP.",
        "translation_ro": "Aș vrea să fac o programare la medicul de familie.",
        "topic": "healthcare",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "I'd",
                "sounds_like": "/aɪd/",
                "explanation_ro": "„I would” devine „I'd”, iar „d”-ul abia se aude înainte de „like”.",
            },
            {
                "pattern": "linking",
                "fragment": "book an appointment",
                "sounds_like": "",
                "explanation_ro": "„book‿an‿appointment” curge legat: „boo-ka-nappointment”.",
            },
        ],
    },
    {
        "text": "How long have you had the cough?",
        "translation_ro": "De cât timp aveți tusea?",
        "topic": "healthcare",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "have you",
                "sounds_like": "/əv jə/",
                "explanation_ro": "„have” își pierde „h”-ul și devine /əv/, deci pare „long-əv-yə”.",
            },
        ],
    },
    {
        "text": "Take two of these twice a day after food.",
        "translation_ro": "Luați câte două de două ori pe zi, după masă.",
        "topic": "healthcare",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "of",
                "sounds_like": "/əv/",
                "explanation_ro": "„of” devine /əv/, deci „two of these” pare „tuə these”.",
            },
            {
                "pattern": "linking",
                "fragment": "twice a day",
                "sounds_like": "",
                "explanation_ro": "„s”-ul se leagă de „a”: „twi‿sa day”, ca un singur cuvânt.",
            },
        ],
    },
    {
        "text": "Is it painful when I press here?",
        "translation_ro": "Vă doare când apăs aici?",
        "topic": "healthcare",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "linking",
                "fragment": "when I",
                "sounds_like": "",
                "explanation_ro": "„n”-ul se leagă de „I”: „whe‿nai press”.",
            },
        ],
    },
    {
        "text": "You'll need to get a prescription from the pharmacy.",
        "translation_ro": "Va trebui să luați o rețetă de la farmacie.",
        "topic": "healthcare",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "You'll",
                "sounds_like": "/juːl/",
                "explanation_ro": "„you will” devine „you'll”, ușor de confundat cu „you” simplu.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "get a",
                "sounds_like": "/ɡeʔ ə/",
                "explanation_ro": "„t”-ul din „get” devine oprire în gât: „ge'a prescription”.",
            },
        ],
    },
    {
        "text": "Can you confirm your date of birth for me?",
        "translation_ro": "Îmi puteți confirma data nașterii?",
        "topic": "healthcare",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "reduced-function-word",
                "fragment": "your",
                "sounds_like": "/jə/",
                "explanation_ro": "„your” devine /jə/ și aproape dispare între „confirm” și „date”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "of",
                "sounds_like": "/əv/",
                "explanation_ro": "„of” devine /əv/, iar „date of birth” se aude ca o singură expresie.",
            },
        ],
    },
    {
        "text": "There's no need to worry, it's quite common.",
        "translation_ro": "Nu e cazul să vă îngrijorați, e destul de frecvent.",
        "topic": "healthcare",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "There's",
                "sounds_like": "/ðeəz/",
                "explanation_ro": "„there is” devine „there's”, pronunțat scurt, aproape „thez”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "quite common",
                "sounds_like": "/kwaɪʔ ˈkɒmən/",
                "explanation_ro": "„t”-ul din „quite” e înlocuit de o oprire în gât: „quai' common”.",
            },
        ],
    },
    # -------------------------------------------------------------------- school
    {
        "text": "What time's pick-up today?",
        "translation_ro": "La ce oră îi luăm (pe copii) azi?",
        "topic": "school",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "What",
                "sounds_like": "/wɒʔ/",
                "explanation_ro": "„t”-ul din „what” devine oprire în gât înainte de „time”: „wo' time”.",
            },
            {
                "pattern": "contraction",
                "fragment": "time's",
                "sounds_like": "/taɪmz/",
                "explanation_ro": "„time is” devine „time's”, iar „is” rămâne doar un „z” lipit de cuvânt.",
            },
        ],
    },
    {
        "text": "Don't forget your PE kit tomorrow.",
        "translation_ro": "Nu uita echipamentul de sport mâine.",
        "topic": "school",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "elision",
                "fragment": "Don't forget",
                "sounds_like": "/dəʊn fəˈɡet/",
                "explanation_ro": "„t”-ul din „don't” dispare înainte de „f”, deci pare „don' forget”.",
            },
            {
                "pattern": "schwa",
                "fragment": "tomorrow",
                "sounds_like": "/təˈmɒrəʊ/",
                "explanation_ro": "Prima silabă e un schwa scurt (/tə/), nu „tu”, deci auzi mai ales „-MOR-”.",
            },
        ],
    },
    {
        "text": "She's got a bit of a cough, so she's off today.",
        "translation_ro": "Tușește puțin, așa că azi stă acasă.",
        "topic": "school",
        "difficulty": 5,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "got a bit of a",
                "sounds_like": "",
                "explanation_ro": "Ambele „t” devin opriri în gât, iar totul se leagă: „go'a bi'ova cough”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "of",
                "sounds_like": "/əv/",
                "explanation_ro": "„of” devine /əv/ sau chiar /ə/, lipit de „bit” și „a”.",
            },
        ],
    },
    {
        "text": "Could you sign the permission slip for the school trip?",
        "translation_ro": "Puteți semna acordul pentru excursia școlară?",
        "topic": "school",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "Could you",
                "sounds_like": "/kʊdʒu/",
                "explanation_ro": "„d” + „y” devin /dʒ/: „could you” sună ca „cugiu”.",
            },
            {
                "pattern": "schwa",
                "fragment": "permission",
                "sounds_like": "/pəˈmɪʃən/",
                "explanation_ro": "„per-” și „-sion” se reduc la schwa, deci auzi mai ales „-MI-”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "for",
                "sounds_like": "/fə/",
                "explanation_ro": "„for” devine /fə/ și se pierde înainte de „the school trip”.",
            },
        ],
    },
    {
        "text": "Has he handed in his homework yet?",
        "translation_ro": "Și-a predat tema?",
        "topic": "school",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "dropped-consonant",
                "fragment": "he",
                "sounds_like": "/i/",
                "explanation_ro": "„h”-ul din „he” neaccentuat cade, deci „has he” sună ca „hazi”.",
            },
            {
                "pattern": "dropped-consonant",
                "fragment": "his",
                "sounds_like": "/ɪz/",
                "explanation_ro": "„his” își pierde „h”-ul și se leagă de „in”: „handed i‿niz homework”.",
            },
        ],
    },
    {
        "text": "What did you get up to at school today?",
        "translation_ro": "Ce ai făcut azi la școală?",
        "topic": "school",
        "difficulty": 4,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "did you",
                "sounds_like": "/dɪdʒə/",
                "explanation_ro": "„did you” devine /dɪdʒə/, iar „what” se lipește de el, deci totul pare un cuvânt.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "get up",
                "sounds_like": "/ɡeʔ ʌp/",
                "explanation_ro": "„t”-ul din „get” devine oprire în gât înainte de „up”: „ge' up”.",
            },
        ],
    },
    # ------------------------------------------------------------------- friends
    {
        "text": "Do you fancy grabbing a coffee?",
        "translation_ro": "Ai chef să bem o cafea?",
        "topic": "friends",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "everyday-reduction",
                "fragment": "Do you",
                "sounds_like": "d'you",
                "explanation_ro": "„do you” se reduce la „d'you” (/djə/), deci întrebarea pare să înceapă cu „fancy”.",
            },
            {
                "pattern": "linking",
                "fragment": "grabbing a",
                "sounds_like": "",
                "explanation_ro": "„a” se lipește de „grabbing”: „grabbinga coffee”.",
            },
        ],
    },
    {
        "text": "You could have told me earlier.",
        "translation_ro": "Puteai să-mi spui mai devreme.",
        "topic": "friends",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "could have",
                "sounds_like": "/kʊdəv/",
                "explanation_ro": "„have” devine /əv/, deci „could have” sună ca „coulda”.",
            },
            {
                "pattern": "elision",
                "fragment": "told me",
                "sounds_like": "/təʊl mi/",
                "explanation_ro": "„d”-ul din „told” dispare înainte de „me”, deci pare „tol' me”.",
            },
        ],
    },
    {
        "text": "I didn't realise you were coming.",
        "translation_ro": "Nu mi-am dat seama că vii.",
        "topic": "friends",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "didn't",
                "sounds_like": "/ˈdɪdn̩/",
                "explanation_ro": "„didn't” e rostit scurt, iar „t”-ul final adesea nu se aude: „didn'”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "were",
                "sounds_like": "/wə/",
                "explanation_ro": "„were” neaccentuat devine /wə/, ușor de confundat cu „was” sau „are”.",
            },
        ],
    },
    {
        "text": "Shall we head off?",
        "translation_ro": "Plecăm?",
        "topic": "friends",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Shall",
                "sounds_like": "/ʃəl/",
                "explanation_ro": "„shall” neaccentuat devine /ʃəl/, aproape „sh'l we”.",
            },
            {
                "pattern": "linking",
                "fragment": "head off",
                "sounds_like": "",
                "explanation_ro": "„d”-ul se leagă de „off”: „hea‿doff”.",
            },
        ],
    },
    {
        "text": "Are you coming to the pub later?",
        "translation_ro": "Vii la pub mai târziu?",
        "topic": "friends",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "reduced-function-word",
                "fragment": "Are you",
                "sounds_like": "/ə jə/",
                "explanation_ro": "„are you” e atât de slab încât întrebarea pare să înceapă cu „coming”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "to",
                "sounds_like": "/tə/",
                "explanation_ro": "„to” devine /tə/ și se leagă de „the pub”.",
            },
        ],
    },
    {
        "text": "I'm absolutely knackered, I'm going to head home.",
        "translation_ro": "Sunt mort de oboseală, mă duc acasă.",
        "topic": "friends",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "everyday-reduction",
                "fragment": "I'm going to",
                "sounds_like": "I'm gonna",
                "explanation_ro": "„I'm going to” se reduce la „I'm gonna”.",
            },
        ],
    },
    {
        "text": "Cheers for sorting that out.",
        "translation_ro": "Mersi că te-ai ocupat de asta.",
        "topic": "friends",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "for",
                "sounds_like": "/fə/",
                "explanation_ro": "„for” devine /fə/, deci „cheers for” sună ca „cheers-fə”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "that out",
                "sounds_like": "/ðæʔ aʊt/",
                "explanation_ro": "„t”-ul din „that” devine oprire în gât înainte de „out”: „tha' out”.",
            },
        ],
    },
    {
        "text": "I saw a mate of mine in town yesterday.",
        "translation_ro": "Am văzut ieri un prieten în oraș.",
        "topic": "friends",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "intrusive-r",
                "fragment": "saw a",
                "sounds_like": "/sɔːr ə/",
                "explanation_ro": "Mulți britanici adaugă un „r” între „saw” și „a”, deși nu e scris: „saw‿r‿a mate”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "of",
                "sounds_like": "/əv/",
                "explanation_ro": "„of” devine /əv/, lipit de „mate”: „mate-ə-mine”.",
            },
        ],
    },
    # ---------------------------------------------------------------- small-talk
    {
        "text": "Lovely weather we're having, isn't it?",
        "translation_ro": "Ce vreme frumoasă avem, nu?",
        "topic": "small-talk",
        "difficulty": 2,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "we're",
                "sounds_like": "/wɪə/",
                "explanation_ro": "„we are” devine „we're”, aproape la fel cu „we” sau „were”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "isn't it",
                "sounds_like": "",
                "explanation_ro": "În întrebarea de final, ambele „t” se pierd adesea în opriri în gât: „izn' i'”.",
            },
        ],
    },
    {
        "text": "It's absolutely chucking it down out there.",
        "translation_ro": "Plouă cu găleata afară.",
        "topic": "small-talk",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "linking",
                "fragment": "chucking it down",
                "sounds_like": "",
                "explanation_ro": "„chucking‿it‿down” se leagă strâns; „it” e abia un „i” scurt.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "out there",
                "sounds_like": "/aʊʔ ðeə/",
                "explanation_ro": "„t”-ul din „out” devine oprire în gât înainte de „there”: „ou' there”.",
            },
        ],
    },
    {
        "text": "Did you have a good weekend?",
        "translation_ro": "Ai avut un weekend plăcut?",
        "topic": "small-talk",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "assimilation",
                "fragment": "Did you",
                "sounds_like": "/dɪdʒu/",
                "explanation_ro": "„d” + „y” se contopesc în /dʒ/: „did you” sună ca „digiu”.",
            },
            {
                "pattern": "linking",
                "fragment": "have a",
                "sounds_like": "",
                "explanation_ro": "„v”-ul se leagă de „a”: „ha‿va good weekend”.",
            },
        ],
    },
    {
        "text": "Not too bad, thanks. And you?",
        "translation_ro": "Nu prea rău, mersi. Tu?",
        "topic": "small-talk",
        "difficulty": 1,
        "patterns": [
            {
                "pattern": "glottal-t",
                "fragment": "Not too",
                "sounds_like": "/nɒʔ tuː/",
                "explanation_ro": "„t”-ul din „not” devine oprire în gât înainte de „too”: „no' too bad”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "And",
                "sounds_like": "/ən/",
                "explanation_ro": "„and” devine /ən/, fără „d”, deci auzi „ən you?”.",
            },
        ],
    },
    {
        "text": "It's supposed to brighten up later.",
        "translation_ro": "Se zice că se înseninează mai târziu.",
        "topic": "small-talk",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "elision",
                "fragment": "supposed to",
                "sounds_like": "/səˈpəʊs tə/",
                "explanation_ro": "„d”-ul din „supposed” dispare înainte de „to”, deci pare „suppos' to”.",
            },
            {
                "pattern": "schwa",
                "fragment": "supposed",
                "sounds_like": "/səˈpəʊzd/",
                "explanation_ro": "Prima silabă e un schwa foarte scurt, uneori chiar dispare: „s'posed”.",
            },
        ],
    },
    {
        "text": "Have you been anywhere nice for your holidays?",
        "translation_ro": "Ai fost undeva frumos în concediu?",
        "topic": "small-talk",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "weak-form",
                "fragment": "Have you",
                "sounds_like": "/əv jə/",
                "explanation_ro": "„have you” e slab și rapid, adesea /əv jə/ fără „h”.",
            },
            {
                "pattern": "reduced-function-word",
                "fragment": "for your",
                "sounds_like": "/fə jə/",
                "explanation_ro": "„for your” se reduce la /fə jə/, două silabe foarte scurte înainte de „holidays”.",
            },
        ],
    },
    {
        "text": "I saw it on the news this morning.",
        "translation_ro": "Am văzut la știri azi-dimineață.",
        "topic": "small-talk",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "intrusive-r",
                "fragment": "saw it",
                "sounds_like": "/sɔːr ɪt/",
                "explanation_ro": "Între „saw” și „it” apare un „r” nescris, deci auzi „saw‿r‿it”.",
            },
            {
                "pattern": "linking",
                "fragment": "it on",
                "sounds_like": "",
                "explanation_ro": "„it‿on” se leagă, iar „t”-ul devine moale sau oprire în gât.",
            },
        ],
    },
    # -------------------------------------------------------------- fast-british
    {
        "text": "Do you know what I mean?",
        "translation_ro": "Înțelegi ce vreau să zic?",
        "topic": "fast-british",
        "difficulty": 4,
        "patterns": [
            {
                "pattern": "fast-phrase",
                "fragment": "Do you know what I mean",
                "sounds_like": "",
                "explanation_ro": "Expresie de umplutură spusă foarte repede, ca un singur bloc; se recunoaște după ritm, nu după cuvinte.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "what I",
                "sounds_like": "/wɒʔ aɪ/",
                "explanation_ro": "„t”-ul din „what” devine oprire în gât înainte de „I”: „wo' I mean”.",
            },
        ],
    },
    {
        "text": "I don't know, to be honest.",
        "translation_ro": "Nu știu, sincer.",
        "topic": "fast-british",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "everyday-reduction",
                "fragment": "I don't know",
                "sounds_like": "dunno",
                "explanation_ro": "„I don't know” se reduce des la „I dunno”, cu „t”-ul și „d”-ul estompate.",
            },
            {
                "pattern": "weak-form",
                "fragment": "to",
                "sounds_like": "/tə/",
                "explanation_ro": "În „to be honest”, „to” e doar /tə/, deci pare „tə-bee-honest”.",
            },
        ],
    },
    {
        "text": "I'm not being funny, but that's a bit much.",
        "translation_ro": "Nu vreau să par nepoliticos, dar e cam mult.",
        "topic": "fast-british",
        "difficulty": 5,
        "patterns": [
            {
                "pattern": "fast-phrase",
                "fragment": "I'm not being funny",
                "sounds_like": "",
                "explanation_ro": "Formulă britanică spusă dintr-o suflare înaintea unei critici; nu are legătură cu umorul.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "not being",
                "sounds_like": "/nɒʔ ˈbiːɪŋ/",
                "explanation_ro": "„t”-ul din „not” devine oprire în gât înainte de „b”: „no' being”.",
            },
        ],
    },
    {
        "text": "Let me know if you need anything.",
        "translation_ro": "Spune-mi dacă ai nevoie de ceva.",
        "topic": "fast-british",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "everyday-reduction",
                "fragment": "Let me",
                "sounds_like": "lemme",
                "explanation_ro": "„let me” se reduce la „lemme”, fără „t”.",
            },
            {
                "pattern": "linking",
                "fragment": "need anything",
                "sounds_like": "",
                "explanation_ro": "„d”-ul se leagă de „anything”: „nee‿danything”.",
            },
        ],
    },
    {
        "text": "I haven't got a clue, mate.",
        "translation_ro": "N-am nici cea mai vagă idee, frate.",
        "topic": "fast-british",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "contraction",
                "fragment": "haven't",
                "sounds_like": "/ˈhævn̩/",
                "explanation_ro": "„haven't” e rostit scurt, iar „t”-ul final adesea dispare înainte de „got”.",
            },
            {
                "pattern": "glottal-t",
                "fragment": "got a",
                "sounds_like": "/ɡɒʔ ə/",
                "explanation_ro": "„got a” devine „go'a”, cu oprire în gât în loc de „t”.",
            },
        ],
    },
    {
        "text": "What do you reckon?",
        "translation_ro": "Tu ce zici?",
        "topic": "fast-british",
        "difficulty": 4,
        "patterns": [
            {
                "pattern": "fast-phrase",
                "fragment": "What do you",
                "sounds_like": "",
                "explanation_ro": "„what do you” se comprimă într-o singură silabă rapidă, iar „reckon” e singurul cuvânt clar.",
            },
        ],
    },
    {
        "text": "I like the idea of it, to be fair.",
        "translation_ro": "Îmi place ideea, ca să fiu corect.",
        "topic": "fast-british",
        "difficulty": 4,
        "patterns": [
            {
                "pattern": "intrusive-r",
                "fragment": "idea of it",
                "sounds_like": "/aɪˈdɪər əv ɪt/",
                "explanation_ro": "Între „idea” și „of” apare un „r” care nu e scris: „idea‿r‿of it”.",
            },
            {
                "pattern": "fast-phrase",
                "fragment": "to be fair",
                "sounds_like": "",
                "explanation_ro": "Expresie de umplutură foarte frecventă, spusă rapid la final, cu „to” redus la /tə/.",
            },
        ],
    },
    {
        "text": "Cheers, mate, see you in a bit.",
        "translation_ro": "Mersi, frate, ne vedem mai încolo.",
        "topic": "fast-british",
        "difficulty": 3,
        "patterns": [
            {
                "pattern": "fast-phrase",
                "fragment": "see you in a bit",
                "sounds_like": "",
                "explanation_ro": "Salut de despărțire spus ca un bloc: „see-ya-na-bi'”, cu „t”-ul final înghițit.",
            },
        ],
    },
    {
        "text": "It's all about law and order these days.",
        "translation_ro": "Acum totul e despre ordine publică.",
        "topic": "fast-british",
        "difficulty": 4,
        "patterns": [
            {
                "pattern": "intrusive-r",
                "fragment": "law and order",
                "sounds_like": "/lɔːr ən ˈɔːdə/",
                "explanation_ro": "Vorbitorii britanici inserează un „r” nescris între „law” și „and”: „law‿r‿and order”.",
            },
            {
                "pattern": "weak-form",
                "fragment": "and",
                "sounds_like": "/ən/",
                "explanation_ro": "„and” devine /ən/, un sunet scurt între „law” și „order”.",
            },
        ],
    },
]
