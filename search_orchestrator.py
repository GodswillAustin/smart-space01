import serpapi
import os
from dotenv import load_dotenv
from database_manager import DatabaseManager

load_dotenv()
KEY = os.getenv("SERPAPI")

client = serpapi.Client(api_key=KEY)

language_dict = {
    "Afrikaans": "af",
    "Akan": "ak",
    "Albanian": "sq",
    "Samoa": "ws",
    "Amharic": "am",
    "Arabic": "ar",
    "Armenian": "hy",
    "Azerbaijani": "az",
    "Basque": "eu",
    "Belarusian": "be",
    "Bemba": "bem",
    "Bengali": "bn",
    "Bihari": "bh",
    "Bork, bork, bork!": "xx-bork",
    "Bosnian": "bs",
    "Breton": "br",
    "Bulgarian": "bg",
    "Bhutanese": "bt",
    "Cambodian": "km",
    "Catalan": "ca",
    "Cherokee": "chr",
    "Chichewa": "ny",
    "Chinese (Simplified)": "zh-cn",
    "Chinese (Traditional)": "zh-tw",
    "Corsican": "co",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "Elmer Fudd": "xx-elmer",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Ewe": "ee",
    "Faroese": "fo",
    "Filipino": "tl",
    "Finnish": "fi",
    "French": "fr",
    "Frisian": "fy",
    "Ga": "gaa",
    "Galician": "gl",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Greenlandic": "kl",
    "Guarani": "gn",
    "Gujarati": "gu",
    "Hacker": "xx-hacker",
    "Haitian Creole": "ht",
    "Hausa": "ha",
    "Hawaiian": "haw",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Igbo": "ig",
    "Indonesian": "id",
    "Interlingua": "ia",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Javanese": "jw",
    "Kannada": "kn",
    "Kazakh": "kk",
    "Kinyarwanda": "rw",
    "Kirundi": "rn",
    "Klingon": "xx-klingon",
    "Kongo": "kg",
    "Korean": "ko",
    "Krio (Sierra Leone)": "kri",
    "Kurdish": "ku",
    "Kurdish (Soranî)": "ckb",
    "Kyrgyz": "ky",
    "Laothian": "lo",
    "Latin": "la",
    "Latvian": "lv",
    "Lingala": "ln",
    "Lithuanian": "lt",
    "Lozi": "loz",
    "Luganda": "lg",
    "Luo": "ach",
    "Macedonian": "mk",
    "Malagasy": "mg",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Maldives": "mv",
    "Maori": "mi",
    "Marathi": "mr",
    "Mauritian Creole": "mfe",
    "Moldavian": "mo",
    "Mongolian": "mn",
    "Montenegrin": "sr-me",
    "Myanmar": "my",
    "Nepali": "ne",
    "Nigerian Pidgin": "pcm",
    "Northern Sotho": "nso",
    "Norwegian": "no",
    "Norwegian (Nynorsk)": "nn",
    "Occitan": "oc",
    "Oriya": "or",
    "Oromo": "om",
    "Pashto": "ps",
    "Persian": "fa",
    "Pirate": "xx-pirate",
    "Polish": "pl",
    "Portuguese": "pt",
    "Portuguese (Brazil)": "pt-br",
    "Portuguese (Portugal)": "pt-pt",
    "Punjabi": "pa",
    "Quechua": "qu",
    "Romanian": "ro",
    "Romansh": "rm",
    "Runyakitara": "nyn",
    "Russian": "ru",
    "Scots Gaelic": "gd",
    "Serbian": "sr",
    "Serbo-Croatian": "sh",
    "Sesotho": "st",
    "Setswana": "tn",
    "Seychellois Creole": "crs",
    "Shona": "sn",
    "Sindhi": "sd",
    "Sinhalese": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Somali": "so",
    "Spanish": "es",
    "Spanish (Latin American)": "es-419",
    "Sundanese": "su",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tajik": "tg",
    "Tamil": "ta",
    "Tatar": "tt",
    "Telugu": "te",
    "Thai": "th",
    "Tigrinya": "ti",
    "Tonga": "to",
    "Tshiluba": "lua",
    "Tumbuka": "tum",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Twi": "tw",
    "Uighur": "ug",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uzbek": "uz",
    "Vanuatu": "vu",
    "Vietnamese": "vi",
    "Welsh": "cy",
    "Wolof": "wo",
    "Xhosa": "xh",
    "Yiddish": "yi",
    "Yoruba": "yo",
    "Zulu": "zu"
}

class WebSearch:
  def __init__(self, user_id, lang, num_result=10):
    self.user_id = user_id
    self.num_result = num_result
    self.DBManager = DatabaseManager(self.user_id)
    self.location = self.DBManager.ph_loc()[1].split("\n")[0].split(", ")[-1]
    self.lang = language_dict[lang] if lang in language_dict else "en"

  def WebContent(self, query):

    def google_ai_search():
      try:
        results = client.search({
          "engine": "google_ai_mode",
          "q": query
        })
        return results.get("text_blocks", None)
      except:
        pass

    def google_search():
      try:
        results = client.search({
          "engine": "google",
          "q": query,
          "location": self.location,
          "google_domain": "google.com",
          "hl": self.lang,
          "num": self.num_result
        })
        return results.get("organic_results", [])
      except:
        pass
    
    return google_ai_search() or google_search() or ["No result"]
   
  def VideoContent(self, query):
    try:
      results = client.search({
        "engine": "youtube",
        "search_query": query,
        "num": self.num_result
      })

      video = results.get("video_results", "")
      movie = results.get("movie_results", "")
      shorts = results.get("shorts_results")[0].get("shorts", "")
      for result in [movie, video, shorts]:
        for item in result:
          item.pop("serpapi_link", None)
          item.pop("video_id", None)
          item.pop("extensions", None)
          item.pop("thumbnail", None)
          item.pop("rich", None)
          item.get("channel").pop("thumbnail") if item.get("channel") else None

      return movie, video, shorts
    except:
      return ["No result"], ["No result"], ["No result"]
    
  def ImageContent(self, query):
    try:
      results = client.search({
        "engine": "google_images",
        "q": query,
        "location": self.location,
        "google_domain": "google.com",
        "hl": self.lang
      })

      search_result = results["images_results"]

      for item in search_result:
        item.pop("thumbnail", None)
        item.pop("related_content_id", None)
        item.pop("serpapi_related_content_link", None)
        item.pop("source", None)
        item.pop("source_logo", None)
        item.pop("title", None)
        item.pop("link", None)

        item["image"] = item.pop("original", None)
        item["image_height"] = item.pop("original_height", None)
        item["image_width"] = item.pop("original_width", None)

      return search_result
    except:
      return ["No result"]