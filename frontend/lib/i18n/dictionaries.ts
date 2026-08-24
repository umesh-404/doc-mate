/**
 * Lightweight dictionary-based i18n for Doc-mate.
 *
 * English (en), Hindi (hi) and Tamil (ta) are scaffolded here. The shape is
 * intentionally flat and typed so every locale must provide every key — the
 * compiler flags a missing translation. Summaries are the primary surface that
 * will need full localisation; UI chrome is covered here as a starting point.
 */

export const locales = ["en", "hi", "ta"] as const;
export type Locale = (typeof locales)[number];

export const localeNames: Record<Locale, string> = {
  en: "English",
  hi: "हिन्दी",
  ta: "தமிழ்",
};

export const defaultLocale: Locale = "en";

export type Dictionary = {
  appName: string;
  tagline: string;
  common: {
    signIn: string;
    signOut: string;
    email: string;
    password: string;
    cancel: string;
    save: string;
    search: string;
    back: string;
    loading: string;
    retry: string;
    error: string;
  };
  roles: {
    reception: string;
    doctor: string;
  };
  login: {
    heading: string;
    subheading: string;
    demoHint: string;
    failed: string;
  };
  nav: {
    patients: string;
    newPatient: string;
  };
  states: {
    loading: string;
    errorTitle: string;
    errorBody: string;
    empty: string;
  };
  patients: {
    subtitleReception: string;
    subtitleDoctor: string;
    searchPlaceholder: string;
    colPatient: string;
    colAbha: string;
    colLanguage: string;
    colRegistered: string;
    open: string;
    emptyTitle: string;
    emptyBody: string;
    noMatch: string;
    loadError: string;
  };
  newPatient: {
    intro: string;
    detailsTitle: string;
    fullName: string;
    abhaId: string;
    abhaHint: string;
    age: string;
    sex: string;
    male: string;
    female: string;
    other: string;
    phone: string;
    preferredLanguage: string;
    summaryTitle: string;
    verifyNote: string;
    create: string;
    creating: string;
    createError: string;
  };
  docs: {
    title: string;
    uploadTitle: string;
    docType: string;
    documentsTitle: string;
    noDocuments: string;
    uploading: string;
    uploadError: string;
    verifyTitle: string;
    extractedItems: string;
    noItemsYet: string;
    processingItems: string;
    failedTitle: string;
    verifyAll: string;
    verifySelected: string;
    verified: string;
    needsVerification: string;
    confidence: string;
    selectAll: string;
    value: string;
    openSnapshot: string;
    types: {
      prescription: string;
      labReport: string;
      dischargeSummary: string;
      scan: string;
      note: string;
      other: string;
    };
  };
  snapshot: {
    title: string;
    readTime: string;
    currentComplaint: string;
    activeProblems: string;
    allergies: string;
    medications: string;
    labs: string;
    encounters: string;
    flags: string;
    noAllergies: string;
    disclaimer: string;
    viewSource: string;
    generateTitle: string;
    generateBody: string;
    generateAction: string;
    generating: string;
    generatingBody: string;
    loadError: string;
    needsVerify: string;
    emptySection: string;
    sampleBanner: string;
    viewSample: string;
    hideSample: string;
  };
};

const en: Dictionary = {
  appName: "Doc-mate",
  tagline: "The full patient picture, in under a minute.",
  common: {
    signIn: "Sign in",
    signOut: "Sign out",
    email: "Email",
    password: "Password",
    cancel: "Cancel",
    save: "Save",
    search: "Search",
    back: "Back",
    loading: "Loading…",
    retry: "Retry",
    error: "Something went wrong",
  },
  roles: {
    reception: "Reception",
    doctor: "Doctor",
  },
  login: {
    heading: "Sign in to Doc-mate",
    subheading: "Patient-context engine for high-volume clinics.",
    demoHint: "Demo accounts: reception@demo.in / doctor@demo.in",
    failed: "Sign in failed. Check your credentials and try again.",
  },
  nav: {
    patients: "Patients",
    newPatient: "New patient",
  },
  states: {
    loading: "Loading…",
    errorTitle: "Couldn't load this",
    errorBody: "The backend didn't respond as expected.",
    empty: "Nothing here yet.",
  },
  patients: {
    subtitleReception: "Register patients and upload their records for processing.",
    subtitleDoctor: "Open a patient to read their snapshot.",
    searchPlaceholder: "Search by name, ID or ABHA",
    colPatient: "Patient",
    colAbha: "ABHA",
    colLanguage: "Language",
    colRegistered: "Registered",
    open: "Open",
    emptyTitle: "No patients yet",
    emptyBody: "Register the first patient to get started.",
    noMatch: "No patients match your search.",
    loadError: "Couldn't load patients.",
  },
  newPatient: {
    intro:
      "Enter what you know, then upload everything available on the next step. The system ingests and indexes it for the doctor.",
    detailsTitle: "Patient details",
    fullName: "Full name",
    abhaId: "ABHA ID",
    abhaHint: "14-digit",
    age: "Age",
    sex: "Sex",
    male: "Male",
    female: "Female",
    other: "Other",
    phone: "Phone",
    preferredLanguage: "Preferred language",
    summaryTitle: "Summary",
    verifyNote:
      "Extracted fields (medications, doses, labs) are shown as proposed and verified before the doctor sees them.",
    create: "Create patient",
    creating: "Creating…",
    createError: "Couldn't create the patient.",
  },
  docs: {
    title: "Records",
    uploadTitle: "Upload records",
    docType: "Document type",
    documentsTitle: "Uploaded documents",
    noDocuments: "No documents uploaded yet.",
    uploading: "Uploading…",
    uploadError: "Upload failed.",
    verifyTitle: "Verify extracted items",
    extractedItems: "Extracted items",
    noItemsYet: "No items extracted from this document.",
    processingItems: "Processing — extracted items will appear here.",
    failedTitle: "This document could not be processed.",
    verifyAll: "Verify all",
    verifySelected: "Verify selected",
    verified: "Verified",
    needsVerification: "⚠ verify",
    confidence: "Confidence",
    selectAll: "Select all",
    value: "Value",
    openSnapshot: "Open doctor snapshot",
    types: {
      prescription: "Prescription",
      labReport: "Lab report",
      dischargeSummary: "Discharge summary",
      scan: "Scan film",
      note: "Typed note",
      other: "Other",
    },
  },
  snapshot: {
    title: "Patient Snapshot",
    readTime: "≈ 45 sec read",
    currentComplaint: "Current complaint",
    activeProblems: "Active problems & chronic conditions",
    allergies: "Allergies",
    medications: "Current medications",
    labs: "Recent labs & trends",
    encounters: "Past encounters",
    flags: "Flags & things to verify",
    noAllergies: "No known allergies on record",
    disclaimer:
      "Summarised from source documents. Doc-mate surfaces and cites — it does not diagnose.",
    viewSource: "View source",
    generateTitle: "No snapshot yet",
    generateBody:
      "Generate a citation-backed summary from this patient's uploaded and verified records.",
    generateAction: "Generate summary",
    generating: "Generating summary…",
    generatingBody: "Retrieving records and assembling the snapshot. This can take a moment.",
    loadError: "Couldn't load the snapshot.",
    needsVerify: "⚠ verify",
    emptySection: "Nothing recorded.",
    sampleBanner: "Sample snapshot — synthetic demo data, not this patient.",
    viewSample: "Preview sample snapshot",
    hideSample: "Hide sample",
  },
};

const hi: Dictionary = {
  appName: "Doc-mate",
  tagline: "मरीज़ की पूरी जानकारी, एक मिनट से भी कम में।",
  common: {
    signIn: "साइन इन करें",
    signOut: "साइन आउट",
    email: "ईमेल",
    password: "पासवर्ड",
    cancel: "रद्द करें",
    save: "सहेजें",
    search: "खोजें",
    back: "वापस",
    loading: "लोड हो रहा है…",
    retry: "पुनः प्रयास करें",
    error: "कुछ गड़बड़ हो गई",
  },
  roles: {
    reception: "रिसेप्शन",
    doctor: "डॉक्टर",
  },
  login: {
    heading: "Doc-mate में साइन इन करें",
    subheading: "अधिक भीड़ वाले क्लिनिकों के लिए मरीज़-संदर्भ इंजन।",
    demoHint: "डेमो खाते: reception@demo.in / doctor@demo.in",
    failed: "साइन इन विफल रहा। कृपया अपनी जानकारी जाँचें।",
  },
  nav: {
    patients: "मरीज़",
    newPatient: "नया मरीज़",
  },
  states: {
    loading: "लोड हो रहा है…",
    errorTitle: "इसे लोड नहीं किया जा सका",
    errorBody: "बैकएंड ने अपेक्षित प्रतिक्रिया नहीं दी।",
    empty: "अभी यहाँ कुछ नहीं है।",
  },
  patients: {
    subtitleReception: "मरीज़ों को पंजीकृत करें और उनके रिकॉर्ड प्रोसेसिंग के लिए अपलोड करें।",
    subtitleDoctor: "स्नैपशॉट पढ़ने के लिए किसी मरीज़ को खोलें।",
    searchPlaceholder: "नाम, आईडी या ABHA से खोजें",
    colPatient: "मरीज़",
    colAbha: "ABHA",
    colLanguage: "भाषा",
    colRegistered: "पंजीकृत",
    open: "खोलें",
    emptyTitle: "अभी कोई मरीज़ नहीं",
    emptyBody: "शुरू करने के लिए पहला मरीज़ पंजीकृत करें।",
    noMatch: "आपकी खोज से कोई मरीज़ मेल नहीं खाता।",
    loadError: "मरीज़ लोड नहीं हो सके।",
  },
  newPatient: {
    intro:
      "जो जानकारी हो वह दर्ज करें, फिर अगले चरण में उपलब्ध सब कुछ अपलोड करें। सिस्टम इसे डॉक्टर के लिए इंडेक्स करता है।",
    detailsTitle: "मरीज़ का विवरण",
    fullName: "पूरा नाम",
    abhaId: "ABHA आईडी",
    abhaHint: "14-अंकीय",
    age: "उम्र",
    sex: "लिंग",
    male: "पुरुष",
    female: "महिला",
    other: "अन्य",
    phone: "फ़ोन",
    preferredLanguage: "पसंदीदा भाषा",
    summaryTitle: "सारांश",
    verifyNote:
      "निकाले गए फ़ील्ड (दवाइयाँ, खुराक, जाँच) प्रस्तावित के रूप में दिखाए जाते हैं और डॉक्टर के देखने से पहले सत्यापित किए जाते हैं।",
    create: "मरीज़ बनाएँ",
    creating: "बनाया जा रहा है…",
    createError: "मरीज़ नहीं बनाया जा सका।",
  },
  docs: {
    title: "रिकॉर्ड",
    uploadTitle: "रिकॉर्ड अपलोड करें",
    docType: "दस्तावेज़ प्रकार",
    documentsTitle: "अपलोड किए गए दस्तावेज़",
    noDocuments: "अभी कोई दस्तावेज़ अपलोड नहीं हुआ।",
    uploading: "अपलोड हो रहा है…",
    uploadError: "अपलोड विफल रहा।",
    verifyTitle: "निकाली गई जानकारी सत्यापित करें",
    extractedItems: "निकाली गई जानकारी",
    noItemsYet: "इस दस्तावेज़ से कोई जानकारी नहीं निकाली गई।",
    processingItems: "प्रोसेसिंग — निकाली गई जानकारी यहाँ दिखेगी।",
    failedTitle: "यह दस्तावेज़ प्रोसेस नहीं किया जा सका।",
    verifyAll: "सभी सत्यापित करें",
    verifySelected: "चयनित सत्यापित करें",
    verified: "सत्यापित",
    needsVerification: "⚠ सत्यापित करें",
    confidence: "विश्वास",
    selectAll: "सभी चुनें",
    value: "मान",
    openSnapshot: "डॉक्टर स्नैपशॉट खोलें",
    types: {
      prescription: "पर्ची",
      labReport: "जाँच रिपोर्ट",
      dischargeSummary: "डिस्चार्ज सारांश",
      scan: "स्कैन फ़िल्म",
      note: "टाइप किया नोट",
      other: "अन्य",
    },
  },
  snapshot: {
    title: "मरीज़ स्नैपशॉट",
    readTime: "≈ 45 सेकंड में पढ़ें",
    currentComplaint: "वर्तमान शिकायत",
    activeProblems: "सक्रिय समस्याएँ और पुरानी स्थितियाँ",
    allergies: "एलर्जी",
    medications: "वर्तमान दवाइयाँ",
    labs: "हाल की जाँच और रुझान",
    encounters: "पिछली मुलाक़ातें",
    flags: "ध्यान देने योग्य बिंदु",
    noAllergies: "रिकॉर्ड में कोई ज्ञात एलर्जी नहीं",
    disclaimer:
      "स्रोत दस्तावेज़ों से सारांशित। Doc-mate जानकारी दिखाता और उद्धृत करता है — निदान नहीं करता।",
    viewSource: "स्रोत देखें",
    generateTitle: "अभी कोई स्नैपशॉट नहीं",
    generateBody:
      "इस मरीज़ के अपलोड और सत्यापित रिकॉर्ड से उद्धरण-समर्थित सारांश बनाएँ।",
    generateAction: "सारांश बनाएँ",
    generating: "सारांश बन रहा है…",
    generatingBody: "रिकॉर्ड प्राप्त कर स्नैपशॉट तैयार किया जा रहा है। कुछ समय लग सकता है।",
    loadError: "स्नैपशॉट लोड नहीं हो सका।",
    needsVerify: "⚠ सत्यापित करें",
    emptySection: "कुछ दर्ज नहीं है।",
    sampleBanner: "नमूना स्नैपशॉट — कृत्रिम डेमो डेटा, यह मरीज़ नहीं।",
    viewSample: "नमूना स्नैपशॉट देखें",
    hideSample: "नमूना छिपाएँ",
  },
};

const ta: Dictionary = {
  appName: "Doc-mate",
  tagline: "நோயாளியின் முழு சித்திரம், ஒரு நிமிடத்திற்குள்.",
  common: {
    signIn: "உள்நுழைக",
    signOut: "வெளியேறு",
    email: "மின்னஞ்சல்",
    password: "கடவுச்சொல்",
    cancel: "ரத்து செய்",
    save: "சேமி",
    search: "தேடு",
    back: "பின்",
    loading: "ஏற்றுகிறது…",
    retry: "மீண்டும் முயற்சி",
    error: "ஏதோ தவறாகிவிட்டது",
  },
  roles: {
    reception: "வரவேற்பு",
    doctor: "மருத்துவர்",
  },
  login: {
    heading: "Doc-mate இல் உள்நுழைக",
    subheading: "அதிக நோயாளர் கொண்ட மருத்துவமனைகளுக்கான நோயாளர்-சூழல் இயந்திரம்.",
    demoHint: "டெமோ கணக்குகள்: reception@demo.in / doctor@demo.in",
    failed: "உள்நுழைவு தோல்வி. உங்கள் விவரங்களைச் சரிபார்க்கவும்.",
  },
  nav: {
    patients: "நோயாளர்கள்",
    newPatient: "புதிய நோயாளர்",
  },
  states: {
    loading: "ஏற்றுகிறது…",
    errorTitle: "இதை ஏற்ற முடியவில்லை",
    errorBody: "பின்தளம் எதிர்பார்த்தபடி பதிலளிக்கவில்லை.",
    empty: "இங்கே இன்னும் எதுவும் இல்லை.",
  },
  patients: {
    subtitleReception: "நோயாளர்களைப் பதிவு செய்து அவர்களின் ஆவணங்களைப் பதிவேற்றவும்.",
    subtitleDoctor: "ஸ்னாப்ஷாட்டைப் படிக்க ஒரு நோயாளரைத் திறக்கவும்.",
    searchPlaceholder: "பெயர், ஐடி அல்லது ABHA மூலம் தேடுக",
    colPatient: "நோயாளர்",
    colAbha: "ABHA",
    colLanguage: "மொழி",
    colRegistered: "பதிவு",
    open: "திற",
    emptyTitle: "இன்னும் நோயாளர்கள் இல்லை",
    emptyBody: "தொடங்க முதல் நோயாளரைப் பதிவு செய்யுங்கள்.",
    noMatch: "உங்கள் தேடலுக்கு நோயாளர் யாரும் இல்லை.",
    loadError: "நோயாளர்களை ஏற்ற முடியவில்லை.",
  },
  newPatient: {
    intro:
      "தெரிந்ததை உள்ளிட்டு, அடுத்த படியில் கிடைக்கும் அனைத்தையும் பதிவேற்றவும். கணினி அதை மருத்துவருக்காக வரிசைப்படுத்துகிறது.",
    detailsTitle: "நோயாளர் விவரங்கள்",
    fullName: "முழுப் பெயர்",
    abhaId: "ABHA ஐடி",
    abhaHint: "14 இலக்கம்",
    age: "வயது",
    sex: "பாலினம்",
    male: "ஆண்",
    female: "பெண்",
    other: "மற்றவை",
    phone: "தொலைபேசி",
    preferredLanguage: "விருப்ப மொழி",
    summaryTitle: "சுருக்கம்",
    verifyNote:
      "பிரித்தெடுக்கப்பட்ட புலங்கள் (மருந்துகள், அளவுகள், பரிசோதனைகள்) முன்மொழிவாகக் காட்டப்பட்டு, மருத்துவர் பார்ப்பதற்கு முன் சரிபார்க்கப்படும்.",
    create: "நோயாளரை உருவாக்கு",
    creating: "உருவாக்குகிறது…",
    createError: "நோயாளரை உருவாக்க முடியவில்லை.",
  },
  docs: {
    title: "பதிவுகள்",
    uploadTitle: "ஆவணங்களைப் பதிவேற்று",
    docType: "ஆவண வகை",
    documentsTitle: "பதிவேற்றப்பட்ட ஆவணங்கள்",
    noDocuments: "இன்னும் ஆவணங்கள் பதிவேற்றப்படவில்லை.",
    uploading: "பதிவேற்றுகிறது…",
    uploadError: "பதிவேற்றம் தோல்வி.",
    verifyTitle: "பிரித்தெடுத்த தகவலைச் சரிபார்க்கவும்",
    extractedItems: "பிரித்தெடுத்த தகவல்கள்",
    noItemsYet: "இந்த ஆவணத்திலிருந்து தகவல் எதுவும் பிரித்தெடுக்கப்படவில்லை.",
    processingItems: "செயலாக்கம் — பிரித்தெடுத்த தகவல்கள் இங்கே தோன்றும்.",
    failedTitle: "இந்த ஆவணத்தைச் செயலாக்க முடியவில்லை.",
    verifyAll: "அனைத்தையும் சரிபார்",
    verifySelected: "தேர்ந்தெடுத்ததைச் சரிபார்",
    verified: "சரிபார்க்கப்பட்டது",
    needsVerification: "⚠ சரிபார்",
    confidence: "நம்பிக்கை",
    selectAll: "அனைத்தையும் தேர்வு",
    value: "மதிப்பு",
    openSnapshot: "மருத்துவர் ஸ்னாப்ஷாட்டைத் திற",
    types: {
      prescription: "மருந்துச்சீட்டு",
      labReport: "பரிசோதனை அறிக்கை",
      dischargeSummary: "வெளியேற்ற சுருக்கம்",
      scan: "ஸ்கேன் படம்",
      note: "தட்டச்சு குறிப்பு",
      other: "மற்றவை",
    },
  },
  snapshot: {
    title: "நோயாளர் ஸ்னாப்ஷாட்",
    readTime: "≈ 45 வினாடி வாசிப்பு",
    currentComplaint: "தற்போதைய புகார்",
    activeProblems: "செயலில் உள்ள பிரச்சினைகள் & நாள்பட்ட நிலைகள்",
    allergies: "ஒவ்வாமைகள்",
    medications: "தற்போதைய மருந்துகள்",
    labs: "சமீபத்திய பரிசோதனைகள் & போக்குகள்",
    encounters: "முந்தைய சந்திப்புகள்",
    flags: "சரிபார்க்க வேண்டியவை",
    noAllergies: "பதிவில் அறியப்பட்ட ஒவ்வாமை இல்லை",
    disclaimer:
      "மூல ஆவணங்களிலிருந்து சுருக்கம். Doc-mate தகவலைக் காட்டி மேற்கோள் காட்டுகிறது — நோயறிதல் செய்யாது.",
    viewSource: "மூலத்தைக் காண்க",
    generateTitle: "இன்னும் ஸ்னாப்ஷாட் இல்லை",
    generateBody:
      "இந்த நோயாளரின் பதிவேற்றப்பட்டு சரிபார்க்கப்பட்ட ஆவணங்களிலிருந்து மேற்கோள் அடிப்படையிலான சுருக்கத்தை உருவாக்குங்கள்.",
    generateAction: "சுருக்கத்தை உருவாக்கு",
    generating: "சுருக்கம் உருவாக்கப்படுகிறது…",
    generatingBody: "பதிவுகளைப் பெற்று ஸ்னாப்ஷாட் தயாராகிறது. சிறிது நேரம் ஆகலாம்.",
    loadError: "ஸ்னாப்ஷாட்டை ஏற்ற முடியவில்லை.",
    needsVerify: "⚠ சரிபார்",
    emptySection: "எதுவும் பதிவு செய்யப்படவில்லை.",
    sampleBanner: "மாதிரி ஸ்னாப்ஷாட் — செயற்கை டெமோ தரவு, இந்த நோயாளர் அல்ல.",
    viewSample: "மாதிரி ஸ்னாப்ஷாட்டைக் காண்க",
    hideSample: "மாதிரியை மறை",
  },
};

export const dictionaries: Record<Locale, Dictionary> = { en, hi, ta };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? dictionaries[defaultLocale];
}
