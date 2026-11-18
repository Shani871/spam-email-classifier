"""Interface text in English, Hindi and Hinglish.

Call `t("English text")` wherever text is shown on screen. The English text is the key,
so pages stay readable and untranslated text falls back to English. Use `{name}`
placeholders and pass values as keyword arguments: `t("{count} emails checked", count=5)`.
tests/test_i18n.py fails if a `t("...")` call in the app has no Hindi or Hinglish entry.
"""
from typing import Dict

LANGUAGES = ("English", "Hindi", "Hinglish")

UI: Dict[str, Dict[str, str]] = {
    # Sidebar and navigation
    "Messages are checked on this server. Nothing is sent to an outside AI service, and nothing is saved unless you turn it on in Settings.": {
        "Hindi": "संदेशों की जांच इसी सर्वर पर होती है। कुछ भी किसी बाहरी AI सेवा को नहीं भेजा जाता, और जब तक आप सेटिंग्स में चालू न करें, कुछ भी सेव नहीं होता।",
        "Hinglish": "Messages isi server par check hote hain. Kuch bhi bahar ki AI service ko nahi bheja jata, aur jab tak aap Settings mein on na karein, kuch save nahi hota."},
    "Check a message": {"Hindi": "संदेश जांचें", "Hinglish": "Message check karein"},
    "More": {"Hindi": "और", "Hinglish": "Aur"},
    "Check": {"Hindi": "जांचें", "Hinglish": "Check"},
    "Result": {"Hindi": "नतीजा", "Hinglish": "Result"},
    "What to do": {"Hindi": "क्या करें", "Hinglish": "Kya karein"},
    "Settings": {"Hindi": "सेटिंग्स", "Hinglish": "Settings"},
    "Advanced": {"Hindi": "उन्नत", "Hinglish": "Advanced"},
    "Paste a message, upload an email or screenshot, or scan your inbox.": {
        "Hindi": "संदेश पेस्ट करें, ईमेल या स्क्रीनशॉट अपलोड करें, या अपना इनबॉक्स स्कैन करें।",
        "Hinglish": "Message paste karein, email ya screenshot upload karein, ya apna inbox scan karein."},
    "The verdict for the last message you checked, and the evidence behind it.": {
        "Hindi": "आपके पिछले जांचे गए संदेश का नतीजा, और उसके पीछे के सबूत।",
        "Hinglish": "Aapke last check kiye message ka result, aur uske peeche ke sabut."},
    "Steps to take for your situation, where to report, and how to correct a wrong result.": {
        "Hindi": "आपकी स्थिति के लिए कदम, शिकायत कहां करें, और गलत नतीजा कैसे सुधारें।",
        "Hinglish": "Aapki situation ke liye steps, report kahan karein, aur galat result kaise theek karein."},
    "Connect your inbox, privacy and saved data, and trusted or blocked senders.": {
        "Hindi": "इनबॉक्स जोड़ें, गोपनीयता और सेव किया गया डेटा, और भरोसेमंद या ब्लॉक किए गए प्रेषक।",
        "Hinglish": "Inbox connect karein, privacy aur saved data, aur trusted ya blocked senders."},
    "Model results, benchmark, batch CSV checks, feedback review and inbox monitor.": {
        "Hindi": "मॉडल के नतीजे, बेंचमार्क, CSV से कई संदेशों की जांच, फीडबैक समीक्षा और इनबॉक्स मॉनिटर।",
        "Hinglish": "Model results, benchmark, CSV se bulk check, feedback review aur inbox monitor."},
    "This page is available in English only.": {
        "Hindi": "यह पेज सिर्फ़ अंग्रेज़ी में उपलब्ध है।", "Hinglish": "Yeh page sirf English mein hai."},

    # Shared result elements
    "Check a message first. Your result and next steps will appear here.": {
        "Hindi": "पहले कोई संदेश जांचें। आपका नतीजा और अगले कदम यहां दिखेंगे।",
        "Hinglish": "Pehle koi message check karein. Aapka result aur agle steps yahan dikhenge."},
    "Likely a scam": {"Hindi": "शायद धोखाधड़ी है", "Hinglish": "Shayad scam hai"},
    "Don't click links, reply, pay, or share codes or passwords.": {
        "Hindi": "लिंक न खोलें, जवाब न दें, पैसे न भेजें, और कोई कोड या पासवर्ड साझा न करें।",
        "Hinglish": "Link na kholein, reply na karein, paise na bhejein, aur koi code ya password share na karein."},
    "Check before you act": {"Hindi": "कुछ करने से पहले पुष्टि करें", "Hinglish": "Kuch karne se pehle verify karein"},
    "Confirm with the sender using a phone number or website you already trust.": {
        "Hindi": "भेजने वाले से उस फ़ोन नंबर या वेबसाइट के ज़रिए पुष्टि करें जिस पर आपको पहले से भरोसा है।",
        "Hinglish": "Sender se us phone number ya website se confirm karein jis par aapko pehle se bharosa hai."},
    "No warning signs found": {"Hindi": "कोई चेतावनी संकेत नहीं मिला", "Hinglish": "Koi warning sign nahi mila"},
    "It looks normal. Stay careful with links and payment requests as usual.": {
        "Hindi": "यह सामान्य लगता है। लिंक और भुगतान के अनुरोधों पर हमेशा की तरह सावधान रहें।",
        "Hinglish": "Yeh normal lagta hai. Links aur payment requests par hamesha ki tarah dhyan rakhein."},
    "Not enough to go on": {"Hindi": "जांच के लिए पर्याप्त जानकारी नहीं", "Hinglish": "Check karne ke liye kaafi jaankari nahi"},
    "Add more of the message, or the sender's address, and check again.": {
        "Hindi": "संदेश का और हिस्सा या भेजने वाले का पता जोड़कर फिर से जांचें।",
        "Hinglish": "Message ka aur hissa ya sender ka address add karke dobara check karein."},
    "Risk indicator": {"Hindi": "जोखिम सूचक", "Hinglish": "Risk indicator"},
    "Higher means more warning signs were found. It is an indicator, not a guarantee.": {
        "Hindi": "ज़्यादा स्कोर का मतलब ज़्यादा चेतावनी संकेत। यह एक संकेतक है, गारंटी नहीं।",
        "Hinglish": "Score zyada matlab zyada warning signs mile. Yeh indicator hai, guarantee nahi."},
    "Quotes from the message and some technical details stay in their original language.": {
        "Hindi": "संदेश के उद्धरण और कुछ तकनीकी विवरण मूल भाषा में ही रहते हैं।",
        "Hinglish": "Message ke quotes aur kuch technical details original language mein hi rehte hain."},
    "Download this result": {"Hindi": "यह नतीजा डाउनलोड करें", "Hinglish": "Yeh result download karein"},

    # Check page
    "Is this message safe?": {"Hindi": "क्या यह संदेश सुरक्षित है?", "Hinglish": "Kya yeh message safe hai?"},
    "Check an email, text, job offer or payment request before you click, reply or pay.": {
        "Hindi": "क्लिक करने, जवाब देने या पैसे भेजने से पहले कोई ईमेल, मैसेज, नौकरी का ऑफ़र या भुगतान अनुरोध जांचें।",
        "Hinglish": "Click, reply ya payment karne se pehle email, message, job offer ya payment request check karein."},
    "Paste text": {"Hindi": "टेक्स्ट पेस्ट करें", "Hinglish": "Text paste karein"},
    "Email file": {"Hindi": "ईमेल फ़ाइल", "Hinglish": "Email file"},
    "Screenshot or QR": {"Hindi": "स्क्रीनशॉट या QR", "Hinglish": "Screenshot ya QR"},
    "My inbox": {"Hindi": "मेरा इनबॉक्स", "Hinglish": "Mera inbox"},
    "Where is the message?": {"Hindi": "संदेश कहां है?", "Hinglish": "Message kahan hai?"},
    "General": {"Hindi": "सामान्य", "Hinglish": "General"},
    "Job or internship": {"Hindi": "नौकरी या इंटर्नशिप", "Hinglish": "Job ya internship"},
    "Invoice or payment": {"Hindi": "बिल या भुगतान", "Hinglish": "Invoice ya payment"},
    "What is it about?": {"Hindi": "यह किस बारे में है?", "Hinglish": "Yeh kis baare mein hai?"},
    "Job and payment messages get extra checks for common scams.": {
        "Hindi": "नौकरी और भुगतान वाले संदेशों में आम धोखाधड़ी के लिए अतिरिक्त जांच होती है।",
        "Hinglish": "Job aur payment messages mein common scams ke liye extra checks hote hain."},
    "Likely scam": {"Hindi": "शायद धोखा", "Hinglish": "Shayad scam"},
    "Check first": {"Hindi": "पहले जांचें", "Hinglish": "Pehle check karein"},
    "Looks normal": {"Hindi": "सामान्य लगता है", "Hinglish": "Normal lagta hai"},
    "Not sure": {"Hindi": "पक्का नहीं", "Hinglish": "Pakka nahi"},
    "Upload an email saved as .eml": {"Hindi": ".eml के रूप में सेव किया गया ईमेल अपलोड करें", "Hinglish": ".eml ke roop mein save kiya email upload karein"},
    "In Gmail: open the message, ⋮ menu, Download message. In Outlook: File, Save as.": {
        "Hindi": "Gmail में: संदेश खोलें, ⋮ मेनू, Download message। Outlook में: File, Save as।",
        "Hinglish": "Gmail mein: message kholein, ⋮ menu, Download message. Outlook mein: File, Save as."},
    "Links are not opened and attachments are not run. Sender headers in a file are treated as claims, not proof.": {
        "Hindi": "लिंक खोले नहीं जाते और अटैचमेंट चलाए नहीं जाते। फ़ाइल में भेजने वाले की जानकारी को दावा माना जाता है, सबूत नहीं।",
        "Hinglish": "Links khole nahi jaate aur attachments run nahi hote. File mein sender ki details ko claim maana jata hai, proof nahi."},
    "(No subject)": {"Hindi": "(कोई विषय नहीं)", "Hinglish": "(Koi subject nahi)"},
    "From {sender}": {"Hindi": "{sender} से", "Hinglish": "{sender} se"},
    "an unknown sender": {"Hindi": "अज्ञात प्रेषक", "Hinglish": "unknown sender"},
    "Read the message text": {"Hindi": "संदेश का टेक्स्ट पढ़ें", "Hinglish": "Message ka text padhein"},
    "No readable message body.": {"Hindi": "पढ़ने लायक संदेश नहीं मिला।", "Hinglish": "Padhne layak message body nahi mili."},
    "{count} attachment(s). Names and types are checked; contents are not scanned.": {
        "Hindi": "{count} अटैचमेंट। नाम और प्रकार जांचे जाते हैं; अंदर की सामग्री स्कैन नहीं होती।",
        "Hinglish": "{count} attachment. Naam aur type check hote hain; andar ka content scan nahi hota."},
    "More options": {"Hindi": "और विकल्प", "Hinglish": "Aur options"},
    "Official website of the employer or supplier": {"Hindi": "कंपनी या सप्लायर की आधिकारिक वेबसाइट", "Hinglish": "Company ya supplier ki official website"},
    "Earlier message in the same conversation": {"Hindi": "इसी बातचीत का पिछला संदेश", "Hinglish": "Isi conversation ka pichhla message"},
    "We compare payment details, sender and links between the two.": {
        "Hindi": "हम दोनों के बीच भुगतान विवरण, भेजने वाले और लिंक की तुलना करते हैं।",
        "Hinglish": "Hum dono ke beech payment details, sender aur links compare karte hain."},
    "Earlier sender address": {"Hindi": "पिछले प्रेषक का पता", "Hinglish": "Pichhle sender ka address"},
    "Earlier reply-to address": {"Hindi": "पिछला reply-to पता", "Hinglish": "Pichhla reply-to address"},
    "Check this email": {"Hindi": "यह ईमेल जांचें", "Hinglish": "Yeh email check karein"},
    "Checking the text, links and sender…": {"Hindi": "टेक्स्ट, लिंक और प्रेषक की जांच हो रही है…", "Hinglish": "Text, links aur sender check ho rahe hain…"},
    "The checker is not set up yet. See Advanced for setup instructions.": {
        "Hindi": "जांच अभी सेट अप नहीं है। सेटअप निर्देश Advanced में देखें।",
        "Hinglish": "Checker abhi set up nahi hai. Setup instructions Advanced mein dekhein."},
    "Scan your recent emails without copying anything. We only read them; nothing is moved or deleted.": {
        "Hindi": "बिना कुछ कॉपी किए अपने हाल के ईमेल स्कैन करें। हम उन्हें सिर्फ़ पढ़ते हैं; कुछ भी हटाया या मिटाया नहीं जाता।",
        "Hinglish": "Bina kuch copy kiye apne recent emails scan karein. Hum sirf padhte hain; kuch move ya delete nahi hota."},
    "Connect your email": {"Hindi": "अपना ईमेल जोड़ें", "Hinglish": "Apna email connect karein"},
    "Email address": {"Hindi": "ईमेल पता", "Hinglish": "Email address"},
    "App password": {"Hindi": "ऐप पासवर्ड", "Hinglish": "App password"},
    "16-character app password": {"Hindi": "16 अक्षरों का ऐप पासवर्ड", "Hinglish": "16 characters ka app password"},
    "Not your normal password. Create one in your email account's security settings; Settings explains how.": {
        "Hindi": "यह आपका सामान्य पासवर्ड नहीं है। इसे अपने ईमेल खाते की सुरक्षा सेटिंग्स में बनाएं; सेटिंग्स पेज में तरीका बताया गया है।",
        "Hinglish": "Yeh aapka normal password nahi hai. Ise email account ki security settings mein banayein; Settings page mein tareeka bataya gaya hai."},
    "Connect": {"Hindi": "जोड़ें", "Hinglish": "Connect karein"},
    "Enter your email address and app password.": {"Hindi": "अपना ईमेल पता और ऐप पासवर्ड डालें।", "Hinglish": "Apna email address aur app password daalein."},
    "Connecting…": {"Hindi": "जोड़ा जा रहा है…", "Hinglish": "Connect ho raha hai…"},
    "Other ways to connect": {"Hindi": "जोड़ने के दूसरे तरीके", "Hinglish": "Connect karne ke aur tareeke"},
    "Try the demo inbox": {"Hindi": "डेमो इनबॉक्स आज़माएं", "Hinglish": "Demo inbox try karein"},
    "Five sample emails, including two scams, so you can see how it works first.": {
        "Hindi": "पांच नमूना ईमेल, जिनमें दो धोखाधड़ी वाले हैं, ताकि आप पहले देख सकें कि यह कैसे काम करता है।",
        "Hinglish": "Paanch sample emails, jinmein do scam hain, taaki aap pehle dekh sakein yeh kaise kaam karta hai."},
    "Open demo inbox": {"Hindi": "डेमो इनबॉक्स खोलें", "Hinglish": "Demo inbox kholein"},
    "Connected: {email} ({provider})": {"Hindi": "जुड़ा हुआ: {email} ({provider})", "Hinglish": "Connected: {email} ({provider})"},
    "Change": {"Hindi": "बदलें", "Hinglish": "Badlein"},
    "How many recent emails": {"Hindi": "हाल के कितने ईमेल", "Hinglish": "Kitne recent emails"},
    "Folder": {"Hindi": "फ़ोल्डर", "Hinglish": "Folder"},
    "Inbox": {"Hindi": "इनबॉक्स", "Hinglish": "Inbox"},
    "Gmail spam": {"Hindi": "Gmail स्पैम", "Hinglish": "Gmail spam"},
    "Only unread": {"Hindi": "सिर्फ़ बिना पढ़े", "Hinglish": "Sirf unread"},
    "Scan emails": {"Hindi": "ईमेल स्कैन करें", "Hinglish": "Emails scan karein"},
    "Reading and checking your emails…": {"Hindi": "आपके ईमेल पढ़े और जांचे जा रहे हैं…", "Hinglish": "Aapke emails padhe aur check kiye ja rahe hain…"},
    "No emails matched this scan.": {"Hindi": "इस स्कैन में कोई ईमेल नहीं मिला।", "Hinglish": "Is scan mein koi email nahi mila."},
    "The scan didn't work: {error}": {"Hindi": "स्कैन नहीं हो सका: {error}", "Hinglish": "Scan nahi ho paya: {error}"},
    "Try reconnecting in Settings, or check that your app password is still valid.": {
        "Hindi": "सेटिंग्स में फिर से जोड़कर देखें, या जांचें कि आपका ऐप पासवर्ड अभी भी मान्य है।",
        "Hinglish": "Settings mein dobara connect karke dekhein, ya check karein ki app password abhi bhi valid hai."},
    "{count} emails checked": {"Hindi": "{count} ईमेल जांचे गए", "Hinglish": "{count} emails check kiye"},
    "Show": {"Hindi": "दिखाएं", "Hinglish": "Dikhayein"},
    "All": {"Hindi": "सभी", "Hinglish": "Sab"},
    "Needs attention": {"Hindi": "ध्यान देने वाले", "Hinglish": "Dhyan dene wale"},
    "Nothing here needs attention.": {"Hindi": "यहां किसी पर ध्यान देने की ज़रूरत नहीं है।", "Hinglish": "Yahan kuch bhi dhyan dene layak nahi hai."},
    "Details": {"Hindi": "विवरण", "Hinglish": "Details"},
    "Checking this email in detail…": {"Hindi": "इस ईमेल की विस्तार से जांच हो रही है…", "Hinglish": "Is email ki detail mein jaanch ho rahi hai…"},
    "The check could not be completed: {error}": {"Hindi": "जांच पूरी नहीं हो सकी: {error}", "Hinglish": "Check poora nahi ho paya: {error}"},
    "Upload a screenshot or a photo of a QR code": {"Hindi": "स्क्रीनशॉट या QR कोड की फ़ोटो अपलोड करें", "Hinglish": "Screenshot ya QR code ki photo upload karein"},
    "Text is read on this server. QR links are shown, never opened. Check the text below before you continue.": {
        "Hindi": "टेक्स्ट इसी सर्वर पर पढ़ा जाता है। QR लिंक दिखाए जाते हैं, खोले नहीं जाते। आगे बढ़ने से पहले नीचे का टेक्स्ट जांच लें।",
        "Hinglish": "Text isi server par padha jata hai. QR links sirf dikhaye jaate hain, khole nahi jaate. Aage badhne se pehle neeche ka text check kar lein."},
    "Your image": {"Hindi": "आपकी तस्वीर", "Hinglish": "Aapki image"},
    "Reading the image…": {"Hindi": "तस्वीर पढ़ी जा रही है…", "Hinglish": "Image padhi ja rahi hai…"},
    "The QR code points to (not opened):": {"Hindi": "QR कोड इस पते पर ले जाता है (खोला नहीं गया):", "Hinglish": "QR code is address par le jata hai (khola nahi gaya):"},
    "Job scam": {"Hindi": "नौकरी का धोखा", "Hinglish": "Job scam"},
    "Fake payment": {"Hindi": "नकली भुगतान", "Hinglish": "Fake payment"},
    "OTP request": {"Hindi": "OTP की मांग", "Hinglish": "OTP request"},
    "No message handy? Try an example": {"Hindi": "कोई संदेश नहीं है? एक उदाहरण आज़माएं", "Hinglish": "Message nahi hai? Ek example try karein"},
    "Message": {"Hindi": "संदेश", "Hinglish": "Message"},
    "Paste the whole message here, including any links. Remove anything private you don't want to share.": {
        "Hindi": "पूरा संदेश लिंक सहित यहां पेस्ट करें। जो निजी जानकारी साझा नहीं करनी, उसे हटा दें।",
        "Hinglish": "Poora message links ke saath yahan paste karein. Jo private details share nahi karni, unhe hata dein."},
    "More options: sender, earlier message, attachment": {"Hindi": "और विकल्प: प्रेषक, पिछला संदेश, अटैचमेंट", "Hinglish": "Aur options: sender, pichhla message, attachment"},
    "Sender's email address": {"Hindi": "भेजने वाले का ईमेल पता", "Hinglish": "Sender ka email address"},
    "We warn if the sender or links don't match it.": {"Hindi": "अगर प्रेषक या लिंक इससे मेल नहीं खाते, तो हम चेतावनी देंगे।", "Hinglish": "Agar sender ya links isse match nahi karte, to hum warning denge."},
    "Compare with an earlier message": {"Hindi": "पिछले संदेश से तुलना करें", "Hinglish": "Pichhle message se compare karein"},
    "Useful for invoices and ongoing conversations: we look for changed bank details, senders, links or new requests.": {
        "Hindi": "बिल और चल रही बातचीत के लिए उपयोगी: हम बदले हुए बैंक विवरण, प्रेषक, लिंक या नए अनुरोध देखते हैं।",
        "Hinglish": "Invoices aur chal rahi conversation ke liye useful: hum badle hue bank details, sender, links ya nayi requests dekhte hain."},
    "Earlier message": {"Hindi": "पिछला संदेश", "Hinglish": "Pichhla message"},
    "Paste an earlier message from the same conversation": {"Hindi": "इसी बातचीत का पिछला संदेश पेस्ट करें", "Hinglish": "Isi conversation ka pichhla message paste karein"},
    "Attachment file name": {"Hindi": "अटैचमेंट फ़ाइल का नाम", "Hinglish": "Attachment file ka naam"},
    "Only the name and type are checked; the file itself is not scanned.": {
        "Hindi": "सिर्फ़ नाम और प्रकार जांचे जाते हैं; फ़ाइल स्कैन नहीं होती।", "Hinglish": "Sirf naam aur type check hote hain; file scan nahi hoti."},
    "Check message": {"Hindi": "संदेश जांचें", "Hinglish": "Message check karein"},
    "Checked on this server. Nothing is sent to an outside AI service or saved unless you choose to.": {
        "Hindi": "जांच इसी सर्वर पर होती है। आपकी अनुमति के बिना कुछ भी बाहरी AI सेवा को नहीं भेजा जाता और न सेव होता है।",
        "Hinglish": "Check isi server par hota hai. Aapki marzi ke bina kuch bhi bahar ki AI service ko nahi jata aur na save hota hai."},
    "Paste a message first, then press Check message.": {
        "Hindi": "पहले संदेश पेस्ट करें, फिर \"संदेश जांचें\" दबाएं।", "Hinglish": "Pehle message paste karein, phir \"Message check karein\" dabayein."},
    "Checking the message…": {"Hindi": "संदेश की जांच हो रही है…", "Hinglish": "Message check ho raha hai…"},
    "The check could not be completed. Check the setup in Advanced.": {
        "Hindi": "जांच पूरी नहीं हो सकी। Advanced में सेटअप देखें।", "Hinglish": "Check poora nahi ho paya. Advanced mein setup dekhein."},

    # Result page
    "Here's what we found": {"Hindi": "हमें यह मिला", "Hinglish": "Humein yeh mila"},
    "Your mail provider confirmed this came from the sender's real domain. That proves who sent it, not that the request is safe.": {
        "Hindi": "आपके ईमेल प्रदाता ने पुष्टि की है कि यह भेजने वाले के असली डोमेन से आया है। इससे पता चलता है कि किसने भेजा, यह नहीं कि अनुरोध सुरक्षित है।",
        "Hinglish": "Aapke email provider ne confirm kiya ki yeh sender ke asli domain se aaya hai. Isse pata chalta hai kisne bheja, yeh nahi ki request safe hai."},
    "What should I do?": {"Hindi": "मुझे क्या करना चाहिए?", "Hinglish": "Mujhe kya karna chahiye?"},
    "Check another message": {"Hindi": "दूसरा संदेश जांचें", "Hinglish": "Doosra message check karein"},
    "Conversation comparison findings": {"Hindi": "बातचीत की तुलना के नतीजे", "Hinglish": "Conversation comparison ke results"},
    "What changed since the earlier message. A change is a reason to double-check, not proof of fraud.": {
        "Hindi": "पिछले संदेश से क्या बदला। बदलाव दोबारा जांचने की वजह है, धोखाधड़ी का सबूत नहीं।",
        "Hinglish": "Pichhle message se kya badla. Badlaav dobara check karne ki wajah hai, fraud ka proof nahi."},
    "This message": {"Hindi": "यह संदेश", "Hinglish": "Yeh message"},
    "Why it matters:": {"Hindi": "यह क्यों ज़रूरी है:", "Hinglish": "Yeh kyun zaroori hai:"},
    "Checklist before you reply": {"Hindi": "जवाब देने से पहले की सूची", "Hinglish": "Reply karne se pehle checklist"},
    "Why": {"Hindi": "क्यों", "Hinglish": "Kyun"},
    "{count} warning sign(s). Quotes are from the message; the advice is ours.": {
        "Hindi": "{count} चेतावनी संकेत। उद्धरण संदेश से हैं; सलाह हमारी है।", "Hinglish": "{count} warning signs. Quotes message se hain; salah hamari hai."},
    "The link text shown to you": {"Hindi": "आपको दिखाया गया लिंक टेक्स्ट", "Hinglish": "Aapko dikhaya gaya link text"},
    "Source: {source}": {"Hindi": "स्रोत: {source}", "Hinglish": "Source: {source}"},
    "Message text": {"Hindi": "संदेश का टेक्स्ट", "Hinglish": "Message text"},
    "Link destination": {"Hindi": "लिंक का पता", "Hinglish": "Link ka address"},
    "Email header (unverified claim)": {"Hindi": "ईमेल हेडर (अपुष्ट दावा)", "Hinglish": "Email header (unverified claim)"},
    "Email headers": {"Hindi": "ईमेल हेडर", "Hinglish": "Email headers"},
    "Attachment metadata": {"Hindi": "अटैचमेंट की जानकारी", "Hinglish": "Attachment details"},
    "Conversation comparison": {"Hindi": "बातचीत की तुलना", "Hinglish": "Conversation comparison"},
    "Supplied context": {"Hindi": "आपकी दी गई जानकारी", "Hinglish": "Aapki di gayi jaankari"},
    "No scam patterns were found in the text, links or attachments.": {
        "Hindi": "टेक्स्ट, लिंक या अटैचमेंट में धोखाधड़ी का कोई पैटर्न नहीं मिला।", "Hinglish": "Text, links ya attachments mein koi scam pattern nahi mila."},
    "We can't confirm who sent it. Be careful with payment or personal details as you normally would.": {
        "Hindi": "हम पुष्टि नहीं कर सकते कि इसे किसने भेजा। भुगतान या निजी जानकारी के साथ हमेशा की तरह सावधान रहें।",
        "Hinglish": "Hum confirm nahi kar sakte ki kisne bheja. Payment ya personal details ke saath hamesha ki tarah dhyan rakhein."},
    "How to check a job offer": {"Hindi": "नौकरी के ऑफ़र की पुष्टि कैसे करें", "Hinglish": "Job offer kaise verify karein"},
    "1. Find the job on the employer's official careers page.\n2. Contact the employer using details you found yourself, not the ones in the message.\n3. Real employers don't ask you to pay to apply, train or join.\n4. Don't send ID documents or bank details until you've confirmed the offer.": {
        "Hindi": "1. नौकरी को कंपनी के आधिकारिक करियर पेज पर खोजें।\n2. कंपनी से उन्हीं संपर्क विवरणों से बात करें जो आपने खुद खोजे हों, संदेश में दिए गए से नहीं।\n3. असली कंपनियां आवेदन, ट्रेनिंग या जॉइन करने के लिए पैसे नहीं मांगतीं।\n4. ऑफ़र की पुष्टि होने तक पहचान पत्र या बैंक विवरण न भेजें।",
        "Hinglish": "1. Job ko company ke official careers page par dhoondhein.\n2. Company se unhi contact details se baat karein jo aapne khud dhoondhe hon, message wale nahi.\n3. Asli companies apply, training ya join karne ke liye paise nahi maangti.\n4. Offer confirm hone tak ID documents ya bank details na bhejein."},
    "Official job scam guidance": {"Hindi": "नौकरी धोखाधड़ी पर आधिकारिक सलाह", "Hinglish": "Job scam par official guidance"},
    "What this check can and can't tell you": {"Hindi": "यह जांच क्या बता सकती है और क्या नहीं", "Hinglish": "Yeh check kya bata sakta hai aur kya nahi"},
    "Technical details": {"Hindi": "तकनीकी विवरण", "Hinglish": "Technical details"},

    # What to do page
    "What to do now": {"Hindi": "अब क्या करें", "Hinglish": "Ab kya karein"},
    "I only received it": {"Hindi": "मुझे सिर्फ़ संदेश मिला है", "Hinglish": "Mujhe sirf message mila hai"},
    "I clicked a link": {"Hindi": "मैंने लिंक पर क्लिक किया", "Hinglish": "Maine link par click kiya"},
    "I shared a password or code": {"Hindi": "मैंने पासवर्ड या कोड साझा किया", "Hinglish": "Maine password ya code share kiya"},
    "I sent money or card details": {"Hindi": "मैंने पैसे या कार्ड की जानकारी भेजी", "Hinglish": "Maine paise ya card details bheje"},
    "What has happened so far?": {"Hindi": "अब तक क्या हुआ है?", "Hinglish": "Ab tak kya hua hai?"},
    "Do this now": {"Hindi": "अभी यह करें", "Hinglish": "Abhi yeh karein"},
    "Report it": {"Hindi": "शिकायत करें", "Hinglish": "Report karein"},
    "India: cybercrime.gov.in or call 1930": {"Hindi": "भारत: cybercrime.gov.in या 1930 पर कॉल करें", "Hinglish": "India: cybercrime.gov.in ya 1930 par call karein"},
    "USA: ReportFraud.ftc.gov": {"Hindi": "अमेरिका: ReportFraud.ftc.gov", "Hinglish": "USA: ReportFraud.ftc.gov"},
    "Elsewhere, report to your national cybercrime authority or local police. If money left your account, call your bank first.": {
        "Hindi": "दूसरे देशों में अपनी राष्ट्रीय साइबर अपराध एजेंसी या स्थानीय पुलिस को सूचित करें। अगर खाते से पैसे गए हैं, तो सबसे पहले बैंक को कॉल करें।",
        "Hinglish": "Doosre deshon mein apni national cybercrime agency ya local police ko report karein. Agar account se paise gaye hain, to sabse pehle bank ko call karein."},
    "Move this email to spam": {"Hindi": "इस ईमेल को स्पैम में भेजें", "Hinglish": "Is email ko spam mein bhejein"},
    "Optional. It moves to your Gmail spam folder and can be undone; nothing is deleted.": {
        "Hindi": "वैकल्पिक। यह आपके Gmail स्पैम फ़ोल्डर में चला जाएगा और इसे वापस किया जा सकता है; कुछ भी मिटाया नहीं जाता।",
        "Hinglish": "Optional. Yeh aapke Gmail spam folder mein chala jayega aur wapas kiya ja sakta hai; kuch delete nahi hota."},
    "Yes, move this email to spam": {"Hindi": "हां, इस ईमेल को स्पैम में भेजें", "Hinglish": "Haan, is email ko spam mein bhejein"},
    "Move to spam": {"Hindi": "स्पैम में भेजें", "Hinglish": "Spam mein bhejein"},
    "Could not confirm the current message state. Reconnect and rescan.": {
        "Hindi": "संदेश की मौजूदा स्थिति की पुष्टि नहीं हो सकी। फिर से जोड़ें और स्कैन करें।",
        "Hinglish": "Message ki current state confirm nahi ho payi. Dobara connect karke scan karein."},
    "Undo last move": {"Hindi": "पिछला बदलाव वापस लें", "Hinglish": "Pichhla move undo karein"},
    "Gmail confirmed that the previous inbox/spam labels were restored.": {
        "Hindi": "Gmail ने पुष्टि की कि पहले वाले इनबॉक्स/स्पैम लेबल वापस आ गए हैं।",
        "Hinglish": "Gmail ne confirm kiya ki pehle wale inbox/spam labels wapas aa gaye hain."},
    "To move this email to spam, use your email app. This connection can read emails but not move them.": {
        "Hindi": "इस ईमेल को स्पैम में भेजने के लिए अपना ईमेल ऐप इस्तेमाल करें। यह कनेक्शन ईमेल पढ़ सकता है, हटा नहीं सकता।",
        "Hinglish": "Is email ko spam mein bhejne ke liye apna email app use karein. Yeh connection emails padh sakta hai, move nahi kar sakta."},
    "Was this result wrong? Tell us": {"Hindi": "क्या यह नतीजा गलत था? हमें बताएं", "Hinglish": "Kya yeh result galat tha? Humein batayein"},
    "Your correction helps improve the checker. Email addresses and phone numbers are hidden automatically; remove names or anything else private before sending.": {
        "Hindi": "आपका सुधार इस जांच को बेहतर बनाता है। ईमेल पते और फ़ोन नंबर अपने आप छिप जाते हैं; भेजने से पहले नाम या दूसरी निजी जानकारी हटा दें।",
        "Hinglish": "Aapka correction checker ko behtar banata hai. Email address aur phone number apne aap chhup jaate hain; bhejne se pehle naam ya baaki private details hata dein."},
    "This message is actually": {"Hindi": "यह संदेश असल में है", "Hinglish": "Yeh message asal mein hai"},
    "Legitimate message": {"Hindi": "असली संदेश", "Hinglish": "Asli message"},
    "Spam message": {"Hindi": "स्पैम संदेश", "Hinglish": "Spam message"},
    "Message text to send (edit out private details)": {"Hindi": "भेजने के लिए संदेश (निजी जानकारी हटा दें)", "Hinglish": "Bhejne ke liye message (private details hata dein)"},
    "Remove any personal names, physical addresses, or confidential details before sending.": {
        "Hindi": "भेजने से पहले नाम, पते या कोई गोपनीय जानकारी हटा दें।", "Hinglish": "Bhejne se pehle naam, address ya koi confidential details hata dein."},
    "Why? (optional)": {"Hindi": "क्यों? (वैकल्पिक)", "Hinglish": "Kyun? (optional)"},
    "e.g. It's a real alert from my bank": {"Hindi": "जैसे: यह मेरे बैंक का असली अलर्ट है", "Hinglish": "Jaise: Yeh mere bank ka asli alert hai"},
    "Kept for up to 30 days and reviewed by an administrator before it is used. You can delete it any time in Settings.": {
        "Hindi": "30 दिन तक रखा जाता है और इस्तेमाल से पहले एक एडमिन इसकी समीक्षा करता है। आप इसे कभी भी सेटिंग्स में मिटा सकते हैं।",
        "Hinglish": "30 din tak rakha jata hai aur use se pehle admin review karta hai. Aap ise kabhi bhi Settings mein delete kar sakte hain."},
    "I agree to share this corrected message with the administrators for review and model training": {
        "Hindi": "मैं इस सुधरे हुए संदेश को समीक्षा और मॉडल ट्रेनिंग के लिए एडमिन के साथ साझा करने के लिए सहमत हूं",
        "Hinglish": "Meri sahmati hai ki yeh corrected message review aur model training ke liye admins ke saath share kiya jaye"},
    "Send correction": {"Hindi": "सुधार भेजें", "Hinglish": "Correction bhejein"},
    "Explicit consent is required to submit a correction.": {
        "Hindi": "सुधार भेजने के लिए आपकी स्पष्ट सहमति ज़रूरी है।", "Hinglish": "Correction bhejne ke liye aapki clear sahmati zaroori hai."},
    "Thanks, your correction was saved. An administrator will review it before it is used.": {
        "Hindi": "धन्यवाद, आपका सुधार सेव हो गया। इस्तेमाल से पहले एक एडमिन इसकी समीक्षा करेगा।",
        "Hinglish": "Shukriya, aapka correction save ho gaya. Use se pehle admin ise review karega."},
    "Actions taken in this session": {"Hindi": "इस सत्र में किए गए काम", "Hinglish": "Is session mein liye gaye actions"},

    # Settings page
    "Your inbox connection, privacy and saved data, and trusted or blocked senders.": {
        "Hindi": "आपका इनबॉक्स कनेक्शन, गोपनीयता और सेव किया गया डेटा, और भरोसेमंद या ब्लॉक किए गए प्रेषक।",
        "Hinglish": "Aapka inbox connection, privacy aur saved data, aur trusted ya blocked senders."},
    "Inbox connection": {"Hindi": "इनबॉक्स कनेक्शन", "Hinglish": "Inbox connection"},
    "Connected:": {"Hindi": "जुड़ा हुआ:", "Hinglish": "Connected:"},
    "Provider: {provider}. We only read emails when you scan; nothing is stored.": {
        "Hindi": "प्रदाता: {provider}। हम ईमेल सिर्फ़ स्कैन करते समय पढ़ते हैं; कुछ भी स्टोर नहीं होता।",
        "Hinglish": "Provider: {provider}. Hum emails sirf scan karte waqt padhte hain; kuch store nahi hota."},
    "Test connection": {"Hindi": "कनेक्शन जांचें", "Hinglish": "Connection test karein"},
    "Checking the connection…": {"Hindi": "कनेक्शन जांचा जा रहा है…", "Hinglish": "Connection check ho raha hai…"},
    "Disconnect": {"Hindi": "डिस्कनेक्ट करें", "Hinglish": "Disconnect karein"},
    "Sign in with Google": {"Hindi": "Google से साइन इन करें", "Hinglish": "Google se sign in karein"},
    "Demo inbox": {"Hindi": "डेमो इनबॉक्स", "Hinglish": "Demo inbox"},
    "Works with Gmail, Outlook, Yahoo, iCloud, Zoho and most other email services. You need an app password, not your normal password.": {
        "Hindi": "Gmail, Outlook, Yahoo, iCloud, Zoho और ज़्यादातर ईमेल सेवाओं के साथ काम करता है। आपको सामान्य पासवर्ड नहीं, ऐप पासवर्ड चाहिए।",
        "Hinglish": "Gmail, Outlook, Yahoo, iCloud, Zoho aur zyadatar email services ke saath kaam karta hai. Aapko normal password nahi, app password chahiye."},
    "Email service": {"Hindi": "ईमेल सेवा", "Hinglish": "Email service"},
    "Detect from my email address": {"Hindi": "मेरे ईमेल पते से पहचानें", "Hinglish": "Mere email address se pehchaanein"},
    "Other (enter server)": {"Hindi": "अन्य (सर्वर डालें)", "Hinglish": "Other (server daalein)"},
    "16 characters; spaces are fine": {"Hindi": "16 अक्षर; स्पेस चल जाएंगे", "Hinglish": "16 characters; spaces chalenge"},
    "Folder (optional)": {"Hindi": "फ़ोल्डर (वैकल्पिक)", "Hinglish": "Folder (optional)"},
    "Folder to read": {"Hindi": "पढ़ने के लिए फ़ोल्डर", "Hinglish": "Padhne ke liye folder"},
    "For example INBOX, [Gmail]/Spam or Junk.": {"Hindi": "जैसे INBOX, [Gmail]/Spam या Junk।", "Hinglish": "Jaise INBOX, [Gmail]/Spam ya Junk."},
    "How do I get an app password?": {"Hindi": "ऐप पासवर्ड कैसे बनाएं?", "Hinglish": "App password kaise banayein?"},
    "An app password is a separate password just for apps like this one. You need 2-step verification turned on first.": {
        "Hindi": "ऐप पासवर्ड सिर्फ़ इस तरह के ऐप्स के लिए एक अलग पासवर्ड होता है। इसके लिए पहले 2-step verification चालू होना चाहिए।",
        "Hinglish": "App password aise apps ke liye ek alag password hota hai. Iske liye pehle 2-step verification on hona chahiye."},
    "Sign in with Google to let the app read your Gmail. You can disconnect at any time.": {
        "Hindi": "ऐप को आपका Gmail पढ़ने देने के लिए Google से साइन इन करें। आप कभी भी डिस्कनेक्ट कर सकते हैं।",
        "Hinglish": "App ko aapka Gmail padhne dene ke liye Google se sign in karein. Aap kabhi bhi disconnect kar sakte hain."},
    "Google sign-in isn't set up on this server yet. Use an app password instead, or ask the administrator.": {
        "Hindi": "इस सर्वर पर Google साइन-इन अभी सेट अप नहीं है। इसकी जगह ऐप पासवर्ड इस्तेमाल करें, या एडमिन से पूछें।",
        "Hinglish": "Is server par Google sign-in abhi set up nahi hai. Iski jagah app password use karein, ya admin se poochhein."},
    "Five sample emails, including two scams, so you can try scanning without connecting your own inbox.": {
        "Hindi": "पांच नमूना ईमेल, जिनमें दो धोखाधड़ी वाले हैं, ताकि आप अपना इनबॉक्स जोड़े बिना स्कैन आज़मा सकें।",
        "Hinglish": "Paanch sample emails, jinmein do scam hain, taaki aap apna inbox connect kiye bina scan try kar sakein."},
    "Privacy and saved data": {"Hindi": "गोपनीयता और सेव किया गया डेटा", "Hinglish": "Privacy aur saved data"},
    "Checks run on this app's server. Message text and images are not saved or sent to an outside AI service.": {
        "Hindi": "जांच इसी ऐप के सर्वर पर होती है। संदेश और तस्वीरें न सेव होती हैं, न किसी बाहरी AI सेवा को भेजी जाती हैं।",
        "Hinglish": "Check isi app ke server par hota hai. Message aur images na save hote hain, na bahar ki AI service ko bheje jaate hain."},
    "Keep a history of my results": {"Hindi": "मेरे नतीजों का इतिहास रखें", "Hinglish": "Mere results ki history rakhein"},
    "Saves category, assessment, score and date only. Message bodies and sender details are excluded.": {
        "Hindi": "सिर्फ़ श्रेणी, नतीजा, स्कोर और तारीख सेव होती है। संदेश और प्रेषक की जानकारी नहीं।",
        "Hinglish": "Sirf category, result, score aur date save hoti hai. Message aur sender details nahi."},
    "Keep history for": {"Hindi": "इतिहास कितने दिन रखें", "Hinglish": "History kitne din rakhein"},
    "1 day": {"Hindi": "1 दिन", "Hinglish": "1 din"},
    "{days} days": {"Hindi": "{days} दिन", "Hinglish": "{days} din"},
    "No assessment summaries saved yet.": {"Hindi": "अभी तक कोई नतीजा सेव नहीं हुआ।", "Hinglish": "Abhi tak koi result save nahi hua."},
    "Corrections you send are deleted after 30 days. Deleting below removes everything immediately.": {
        "Hindi": "आपके भेजे सुधार 30 दिन बाद मिट जाते हैं। नीचे से मिटाने पर सब कुछ तुरंत हट जाता है।",
        "Hinglish": "Aapke bheje corrections 30 din baad delete ho jaate hain. Neeche se delete karne par sab turant hat jaata hai."},
    "Yes, delete my saved history, corrections and sender rules, and clear this session": {
        "Hindi": "हां, मेरा सेव किया इतिहास, सुधार और प्रेषक नियम मिटाएं, और यह सत्र साफ़ करें",
        "Hinglish": "Haan, meri saved history, corrections aur sender rules delete karein, aur yeh session clear karein"},
    "Delete my saved data": {"Hindi": "मेरा सेव किया डेटा मिटाएं", "Hinglish": "Mera saved data delete karein"},
    "Trusted and blocked senders": {"Hindi": "भरोसेमंद और ब्लॉक किए गए प्रेषक", "Hinglish": "Trusted aur blocked senders"},
    "Blocked senders raise the risk score. Trusted senders are still checked: a familiar address can be faked.": {
        "Hindi": "ब्लॉक किए गए प्रेषकों से जोखिम स्कोर बढ़ता है। भरोसेमंद प्रेषकों की भी जांच होती है, क्योंकि जाना-पहचाना पता भी नकली हो सकता है।",
        "Hinglish": "Blocked senders se risk score badhta hai. Trusted senders bhi check hote hain, kyunki jaana-pehchaana address bhi fake ho sakta hai."},
    "Trusted": {"Hindi": "भरोसेमंद", "Hinglish": "Trusted"},
    "Blocked": {"Hindi": "ब्लॉक किए गए", "Hinglish": "Blocked"},
    "None yet": {"Hindi": "अभी कोई नहीं", "Hinglish": "Abhi koi nahi"},
    "Email address or domain": {"Hindi": "ईमेल पता या डोमेन", "Hinglish": "Email address ya domain"},
    "Rule": {"Hindi": "नियम", "Hinglish": "Rule"},
    "Trust": {"Hindi": "भरोसा करें", "Hinglish": "Trust karein"},
    "Block": {"Hindi": "ब्लॉक करें", "Hinglish": "Block karein"},
    "Remove": {"Hindi": "हटाएं", "Hinglish": "Hatayein"},
    "Save": {"Hindi": "सेव करें", "Hinglish": "Save karein"},
    "Enter an email address or domain.": {"Hindi": "कोई ईमेल पता या डोमेन डालें।", "Hinglish": "Koi email address ya domain daalein."},
}


def current_language() -> str:
    try:
        import streamlit as st
        language = st.session_state.get("language", "English")
    except Exception:
        language = "English"
    return language if language in LANGUAGES else "English"


def translate(text: str, language: str = "English", **values) -> str:
    """`text` in `language`, falling back to English; `{name}` placeholders are filled from `values`."""
    result = text if language == "English" else UI.get(text, {}).get(language, text)
    return result.format(**values) if values else result


def t(text: str, **values) -> str:
    """`text` in the language chosen in the sidebar."""
    return translate(text, current_language(), **values)
