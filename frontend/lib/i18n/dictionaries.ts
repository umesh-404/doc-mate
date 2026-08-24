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
  },
};

export const dictionaries: Record<Locale, Dictionary> = { en, hi, ta };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? dictionaries[defaultLocale];
}
