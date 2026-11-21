"""Knowledge base of documents that Indian tenders (GeM / CPWD / e-procurement / state
tenders) usually ask for - with English, Hindi and Hinglish (transliterated) aliases.

* ``strong`` aliases are used both to *detect* a requirement inside a tender and to
  *match* bidder files.
* ``weak`` aliases are used only for matching bidder files (they are too generic to
  detect requirements in tender text, e.g. the word "declaration").
* ``excl`` phrases are blanked out before testing the item, so that e.g.
  "GST Returns.pdf" does not also count as the "GST Registration" document.

All phrases are normalised with :func:`tendermatrix.textutil.normalize_text`, so Hindi
spelling variants (nukta, chandrabindu) are treated alike.
"""
from __future__ import annotations

from dataclasses import dataclass

from .textutil import TextView, normalize_text

CATEGORIES: dict[str, tuple[str, str]] = {
    "fees": ("Fees & Securities", "शुल्क एवं प्रतिभूति"),
    "legal": ("Legal & Registration", "विधिक एवं पंजीकरण"),
    "tax": ("Tax & Statutory", "कर एवं वैधानिक"),
    "finance": ("Financial Capacity", "वित्तीय क्षमता"),
    "experience": ("Experience & Capability", "अनुभव एवं क्षमता"),
    "technical": ("Technical", "तकनीकी"),
    "declaration": ("Declarations & Forms", "घोषणा एवं प्रपत्र"),
    "quality": ("Quality & Compliance", "गुणवत्ता एवं अनुपालन"),
    "resources": ("Manpower & Equipment", "जनशक्ति एवं उपकरण"),
    "other": ("Other", "अन्य"),
}


@dataclass(frozen=True)
class CatalogItem:
    id: str
    category: str
    en: str
    hi: str
    keywords: tuple[str, ...]        # original (display) strong aliases
    strong: tuple[str, ...]          # normalised
    weak: tuple[str, ...]
    excl: tuple[str, ...]

    def find(self, view: TextView) -> str | None:
        """First strong alias found in the view (exclusions removed), else None."""
        v = view.without(self.excl) if self.excl else view
        for ph in self.strong:
            if v.has(ph):
                return ph
        return None

    def category_label(self, lang: str = "en") -> str:
        en, hi = CATEGORIES.get(self.category, CATEGORIES["other"])
        return hi if lang == "hi" else en


def _split(s: str) -> list[str]:
    return [p.strip() for p in s.split("|") if p.strip()]


def _i(id: str, cat: str, en: str, hi: str, a: str, h: str = "", t: str = "",
       w: str = "", x: str = "") -> CatalogItem:
    kws = _split(a) + _split(h) + _split(t)
    norm_strong = tuple(dict.fromkeys(n for n in (normalize_text(k) for k in kws) if n))
    norm_weak = tuple(dict.fromkeys(n for n in (normalize_text(k) for k in _split(w)) if n))
    norm_excl = tuple(dict.fromkeys(n for n in (normalize_text(k) for k in _split(x)) if n))
    return CatalogItem(id, cat, en, hi, tuple(kws), norm_strong, norm_weak, norm_excl)


_ITEMS: list[CatalogItem] = [
    # ------------------------------------------------------------ fees & securities
    _i("tender_fee", "fees", "Tender Document Fee", "निविदा दस्तावेज़ शुल्क",
       "tender fee|tender fees|tender document fee|bid document fee|cost of tender document|cost of bid document|"
       "tender cost|tender processing fee|processing fee|document fee|tender form fee|rfp fee|cost of tender form|tender fee receipt",
       "निविदा शुल्क|निविदा दस्तावेज शुल्क|निविदा प्रपत्र शुल्क|निविदा फीस|टेंडर फीस|टेंडर शुल्क|बिड शुल्क|दस्तावेज शुल्क|निविदा प्रपत्र का मूल्य",
       "nivida shulk|tender shulk|tender fee"),
    _i("emd", "fees", "Earnest Money Deposit (EMD) / Bid Security", "अग्रिम धरोहर राशि (EMD) / बिड प्रतिभूति",
       "emd|earnest money|earnest money deposit|bid security|bid bond|emd receipt|emd dd|emd bg|emd details|security deposit emd",
       "बयाना राशि|धरोहर राशि|अग्रिम धनराशि|अग्रिम धरोहर राशि|अमानत राशि|अर्नेस्ट मनी|ईएमडी|बिड सिक्योरिटी|बिड प्रतिभूति|अग्रिम राशि|बयाना",
       "bayana rashi|dharohar rashi|amanat rashi",
       x="bid securing declaration|bid security declaration|emd exemption|exemption from emd|emd exemption certificate"),
    _i("bid_sec_decl", "fees", "Bid Securing Declaration / EMD Exemption Proof", "बिड प्रतिभूति घोषणा / EMD छूट प्रमाण",
       "bid securing declaration|bid security declaration|emd exemption|exemption from emd|emd exemption certificate|"
       "exemption from payment of emd|emd waiver",
       "बिड प्रतिभूति घोषणा|बिड सिक्योरिंग घोषणा|ईएमडी छूट|अग्रिम राशि से छूट|ईएमडी से छूट"),

    # ------------------------------------------------------------ legal & registration
    _i("poa", "legal", "Power of Attorney / Authorization Letter (Authorised Signatory)",
       "मुख्तारनामा / अधिकार पत्र (अधिकृत हस्ताक्षरकर्ता)",
       "power of attorney|poa|authorization letter|authorisation letter|authority letter|authorized signatory|authorised signatory|"
       "board resolution|letter of authority|signing authority|authority to sign",
       "मुख्तारनामा|मुख्तार नामा|पावर ऑफ अटॉर्नी|अधिकार पत्र|प्राधिकार पत्र|अधिकृत हस्ताक्षरकर्ता|प्राधिकृत हस्ताक्षरकर्ता|बोर्ड प्रस्ताव|हस्ताक्षर करने का अधिकार",
       "mukhtarnama|mukhtar nama|adhikar patra|pradhikar patra",
       x="oem authorization|oem authorisation|manufacturer authorization|manufacturer authorisation|manufacturers authorization|maf"),
    _i("incorporation", "legal", "Certificate of Incorporation / Firm Registration / Partnership Deed",
       "निगमन प्रमाण पत्र / फर्म पंजीकरण / भागीदारी विलेख",
       "certificate of incorporation|incorporation certificate|firm registration|firm registration certificate|company registration|"
       "company registration certificate|registration of firm|registration of company|partnership deed|partnership agreement|"
       "memorandum of association|articles of association|moa|aoa|llp agreement|registrar of companies|certificate of registration of firm|"
       "proprietorship|partnership firm|legal status|constitution of firm|constitution of the firm",
       "निगमन प्रमाण पत्र|निगमन प्रमाणपत्र|फर्म पंजीकरण|फर्म का पंजीकरण|साझेदारी विलेख|भागीदारी विलेख|पार्टनरशिप डीड|कंपनी पंजीकरण|संस्था पंजीकरण|कंपनी रजिस्ट्रार|पंजीयन प्रमाण पत्र",
       "panjikaran praman patra|firm panjikaran|partnership deed|company incorporation"),
    _i("pan", "tax", "PAN Card (Permanent Account Number)", "पैन कार्ड (स्थायी खाता संख्या)",
       "pan|pan card|permanent account number|pan copy|pan number|pan no|income tax pan",
       "पैन|पैन कार्ड|स्थायी खाता संख्या|पैन नंबर",
       "pan card"),
    _i("gst_reg", "tax", "GST Registration Certificate (GSTIN)", "जीएसटी पंजीकरण प्रमाण पत्र (GSTIN)",
       "gst registration|gst registration certificate|gst certificate|gstin|gst number|gst reg|goods and services tax registration|"
       "gst no|gst",
       "जीएसटी पंजीकरण|जीएसटी प्रमाण पत्र|जीएसटी पंजीयन|जीएसटीआईएन|वस्तु एवं सेवा कर पंजीकरण|जीएसटी",
       "gst praman patra|gst certificate",
       x="gst return|gst returns|gstr|gst filing|gst challan|gst invoice|gst paid|gst extra|gst percentage|gst rate|gst as applicable|gst at"),
    _i("gst_returns", "tax", "GST Returns (GSTR-1 / GSTR-3B)", "जीएसटी रिटर्न (GSTR-1 / GSTR-3B)",
       "gst return|gst returns|gstr|gstr 1|gstr 3b|gst filing|gst returns filed|gst challan|gst return filed",
       "जीएसटी रिटर्न|जीएसटी विवरणी|जीएसटीआर|जीएसटी रिटर्न दाखिल",
       "gst rtn|gst return"),
    _i("itr", "tax", "Income Tax Returns (ITR)", "आयकर रिटर्न (ITR)",
       "income tax return|income tax returns|itr|itr v|it return|it returns|income tax assessment|income tax clearance|26as|tax audit report|form 26as",
       "आयकर रिटर्न|आयकर विवरणी|आईटीआर|आयकर निर्धारण|आयकर क्लीयरेंस|आयकर दाखिल",
       "aaykar return|income tax rtn"),
    _i("labour_licence", "legal", "Labour Licence / Contractor Licence", "श्रम लाइसेंस / ठेकेदार लाइसेंस",
       "labour licence|labour license|labor license|labor licence|contract labour licence|contract labour license|clra|contractor licence|"
       "contractor license|contractor registration|electrical contractor licence|electrical contractor license|licence under contract labour",
       "श्रम लाइसेंस|श्रम अनुज्ञप्ति|ठेकेदार लाइसेंस|ठेकेदार पंजीकरण|ठेका श्रम|श्रमिक लाइसेंस|ठेकेदार अनुज्ञप्ति",
       "shram licence|shram license|thekedar licence"),
    _i("epf", "tax", "EPF Registration / Code", "ईपीएफ पंजीकरण / कोड",
       "epf|pf registration|provident fund|epfo|pf code|epf registration|epf code|employees provident fund|pf challan|pf",
       "भविष्य निधि|ईपीएफ|ईपीएफओ|पीएफ पंजीकरण|कर्मचारी भविष्य निधि|पीएफ कोड",
       "pf praman patra"),
    _i("esic", "tax", "ESIC Registration / Code", "ईएसआईसी पंजीकरण / कोड",
       "esic|esi registration|esi code|employees state insurance|esi|esic registration|esic code",
       "कर्मचारी राज्य बीमा|ईएसआईसी|ईएसआई पंजीकरण|ईएसआई कोड|ईएसआई",
       "esi praman patra"),
    _i("msme", "legal", "MSME / Udyam / NSIC Registration", "एमएसएमई / उद्यम / एनएसआईसी पंजीकरण",
       "msme|udyam|udyam registration|udyam certificate|udyog aadhaar|nsic|ssi registration|micro and small enterprise|micro small enterprises|"
       "msme certificate|udyam aadhaar|sme certificate|msme registration",
       "एमएसएमई|उद्यम पंजीकरण|उद्यम प्रमाण पत्र|उद्योग आधार|लघु उद्योग|सूक्ष्म एवं लघु उद्यम|एनएसआईसी|उद्यम",
       "udyam praman patra|udyog aadhar"),
    _i("startup", "legal", "Startup Recognition (DPIIT)", "स्टार्टअप मान्यता (DPIIT)",
       "startup recognition|dpiit|startup india|recognised startup|recognized startup|start up recognition|startup certificate",
       "स्टार्टअप मान्यता|स्टार्टअप प्रमाण पत्र|डीपीआईआईटी|स्टार्ट अप मान्यता",
       "startup manyata"),
    _i("local_content", "quality", "Make in India / Local Content Certificate (Local Supplier)",
       "मेक इन इंडिया / स्थानीय सामग्री प्रमाण पत्र",
       "make in india|local content|local content certificate|class i local supplier|class 1 local supplier|mii certificate|"
       "preference to make in india|ppp mii|percentage of local content|domestic value addition|purchase preference|mii|local supplier",
       "मेक इन इंडिया|स्थानीय सामग्री|स्थानीय आपूर्तिकर्ता|घरेलू मूल्य संवर्धन|लोकल कंटेंट|क्रय वरीयता|मेक इन इंडिया प्रमाण पत्र",
       "make in india praman patra|local content praman"),

    # ------------------------------------------------------------ financial capacity
    _i("balance_sheet", "finance", "Audited Balance Sheet & Profit/Loss Account (Financial Statements)",
       "लेखा परीक्षित तुलन पत्र एवं लाभ-हानि खाता",
       "audited balance sheet|balance sheet|profit and loss|profit loss account|p and l|financial statements|audited financial statements|"
       "annual report|financial statement|audited accounts|audited account|annual accounts|profit and loss account|p and l account",
       "तुलन पत्र|तुलनपत्र|बैलेंस शीट|लाभ हानि खाता|लाभ एवं हानि|लाभ-हानि|लेखा परीक्षित|वित्तीय विवरण|वार्षिक रिपोर्ट|अंकेक्षित तुलन पत्र",
       "balance sheet|laabh haani|labh hani"),
    _i("turnover", "finance", "Annual Turnover Certificate (CA Certified)", "वार्षिक टर्नओवर प्रमाण पत्र (सीए प्रमाणित)",
       "turnover certificate|annual turnover|average annual turnover|turnover|financial turnover|turnover statement|turn over|"
       "turnover details|turnover of the firm",
       "वार्षिक टर्नओवर|वार्षिक आवर्त|आवर्त प्रमाण पत्र|टर्नओवर प्रमाण पत्र|टर्नओवर|वार्षिक कारोबार|औसत वार्षिक आवर्त",
       "turnover praman patra"),
    _i("net_worth", "finance", "Net Worth Certificate", "निवल मूल्य प्रमाण पत्र",
       "net worth|networth|net worth certificate|positive net worth|net-worth",
       "निवल मूल्य|नेटवर्थ|शुद्ध मूल्य|निवल संपत्ति|निवल मूल्य प्रमाण पत्र|नेट वर्थ",
       "net worth praman patra"),
    _i("solvency", "finance", "Solvency Certificate / Banker's Certificate", "शोधन क्षमता प्रमाण पत्र / बैंकर प्रमाण पत्र",
       "solvency certificate|solvency|bank solvency|banker certificate|bankers certificate|banker s certificate|bank certificate|bank reference|credit worthiness|creditworthiness",
       "शोधन क्षमता|सॉल्वेंसी|सॉल्वेंसी प्रमाण पत्र|बैंक प्रमाण पत्र|ऋण शोधन|शोधन क्षमता प्रमाण पत्र|बैंकर प्रमाण पत्र",
       "solvency praman patra|solvency certificate"),
    _i("bank_details", "finance", "Bank Details / Cancelled Cheque / NEFT Mandate", "बैंक विवरण / निरस्त चेक / NEFT",
       "cancelled cheque|canceled cheque|cancel cheque|bank details|bank account details|bank mandate|neft mandate|ecs mandate|bank passbook|passbook|bank account proof",
       "निरस्त चेक|रद्द चेक|कैंसिल चेक|बैंक विवरण|बैंक खाता विवरण|बैंक पासबुक|रद्द किया हुआ चेक",
       "cancel cheque|bank vivaran"),
    _i("insurance", "finance", "Insurance Policy / Certificate (CAR / Workmen Compensation / Third-party)",
       "बीमा पॉलिसी / प्रमाण पत्र",
       "insurance policy|insurance certificate|workmen compensation|contractor all risk|car policy|third party insurance|professional indemnity|insurance cover",
       "बीमा पॉलिसी|बीमा प्रमाण पत्र|कर्मकार क्षतिपूर्ति|बीमा कवर|बीमा",
       "bima policy"),

    # ------------------------------------------------------------ experience & capability
    _i("experience", "experience", "Experience Certificate / Work Completion Certificate",
       "अनुभव प्रमाण पत्र / कार्य पूर्णता प्रमाण पत्र",
       "experience certificate|experience certificates|completion certificate|work completion certificate|completion certificates|"
       "work experience|past experience|similar work|similar works|similar nature|work done certificate|satisfactory completion|"
       "performance certificate|client certificate|satisfactory performance|previous experience|experience|similar projects|similar supply",
       "अनुभव प्रमाण पत्र|अनुभव प्रमाणपत्र|कार्य पूर्णता प्रमाण पत्र|कार्य अनुभव|समान कार्य|समान प्रकृति|कार्य पूर्णता|पूर्व अनुभव|संतोषजनक कार्य|अनुभव",
       "anubhav praman patra|anubhav pramaan patra|karya anubhav|anubhav patra"),
    _i("work_orders", "experience", "Work Orders / Purchase Orders / Contract Copies (Past)",
       "कार्य आदेश / क्रय आदेश / अनुबंध प्रतियाँ",
       "work order|work orders|purchase order|purchase orders|po copy|wo copy|supply order|supply orders|contract copy|letter of award|loa|"
       "letter of acceptance|agreement copy|copy of contract|copy of agreement|work award",
       "कार्य आदेश|क्रय आदेश|आपूर्ति आदेश|अनुबंध पत्र|स्वीकृति पत्र|कार्यादेश|कार्य आवंटन पत्र",
       "karya adesh|kray adesh|karyadesh"),
    _i("client_list", "experience", "List of Clients / Past Performance Statement", "ग्राहकों की सूची / पूर्व निष्पादन विवरण",
       "list of clients|client list|customer list|list of customers|past performance|performance statement|details of similar works|"
       "statement of works executed|list of works|projects executed|list of projects|reference list|list of orders executed|works executed",
       "ग्राहक सूची|ग्राहकों की सूची|कार्यों की सूची|निष्पादित कार्य|किए गए कार्यों का विवरण|पूर्व निष्पादन|संदर्भ सूची",
       "client suchi|grahak suchi"),
    _i("company_profile", "experience", "Company Profile / Bidder Details", "कंपनी प्रोफाइल / बोलीदाता विवरण",
       "company profile|firm profile|bidder profile|bidder details|company details|organisation details|organization details|"
       "details of the bidder|particulars of the bidder|bidder information form|company brochure",
       "कंपनी प्रोफाइल|फर्म का विवरण|बोलीदाता विवरण|निविदाकार का विवरण|संस्था परिचय|फर्म प्रोफाइल|कंपनी का परिचय",
       "company parichay|firm profile",
       w="general information|about us"),
    _i("no_litigation", "declaration", "No Litigation / Arbitration Declaration", "मुकदमा / मध्यस्थता नहीं होने की घोषणा",
       "litigation|arbitration|court case|no pending litigation|no litigation certificate|legal proceedings|pending litigation|litigation history",
       "मुकदमा|वाद|न्यायालय|मध्यस्थता|मुकदमेबाजी|कोई मुकदमा नहीं|विधिक कार्यवाही",
       "mukadma|no litigation"),
    _i("trade_licence", "legal", "Trade Licence / Shops & Establishment Certificate", "व्यापार लाइसेंस / दुकान एवं स्थापना प्रमाण पत्र",
       "trade licence|trade license|shop and establishment|shops and establishment|shop act|gumasta|municipal licence|municipal license|shops establishment",
       "व्यापार लाइसेंस|दुकान एवं स्थापना|गुमास्ता|ट्रेड लाइसेंस|नगर निगम लाइसेंस|दुकान स्थापना अधिनियम",
       "gumasta praman patra|vyapar licence"),

    # ------------------------------------------------------------ technical
    _i("oem_auth", "technical", "OEM / Manufacturer Authorization Certificate (MAF)", "निर्माता प्राधिकरण प्रमाण पत्र (MAF)",
       "maf|oem authorization|oem authorisation|manufacturer authorization|manufacturer authorisation|manufacturers authorization form|"
       "authorized dealer|authorised dealer|authorized distributor|authorised distributor|authorized reseller|authorised partner|"
       "authorization from oem|dealer certificate|distributor certificate|oem certificate|authorised channel partner|authorized service provider|oem letter",
       "निर्माता प्राधिकरण|निर्माता अधिकार पत्र|अधिकृत विक्रेता|अधिकृत डीलर|अधिकृत वितरक|ओईएम प्राधिकरण|मूल उपकरण निर्माता|निर्माता प्राधिकार",
       "nirmata adhikar patra|oem authorisation"),
    _i("tech_spec", "technical", "Technical Specification Compliance Statement", "तकनीकी विनिर्देश अनुपालन विवरण",
       "technical specification|technical specifications|tech specs|tech spec|compliance statement|compliance sheet|technical compliance|"
       "specification compliance|spec compliance|compliance to technical specifications|technical parameters|technical specification compliance",
       "तकनीकी विनिर्देश|तकनीकी विशिष्टि|अनुपालन विवरण|तकनीकी अनुपालन|तकनीकी विनिर्देशन|विनिर्देश अनुपालन",
       "takniki vinirdesh|technical compliance"),
    _i("datasheet", "technical", "Product Catalogue / Datasheet / Brochure", "उत्पाद सूची / डेटाशीट / ब्रोशर",
       "catalogue|catalog|datasheet|data sheet|brochure|product literature|technical literature|leaflet|product catalogue|product catalog",
       "कैटलॉग|ब्रोशर|डेटाशीट|उत्पाद पुस्तिका|तकनीकी साहित्य|उत्पाद सूची|कैटलोग",
       "catalogue|brochure"),
    _i("test_report", "technical", "Test Reports / Type Test Certificates", "परीक्षण रिपोर्ट / प्रकार परीक्षण प्रमाण पत्र",
       "test report|test reports|type test|type test report|type test certificate|lab test|nabl|nabl accredited|calibration certificate|"
       "routine test|test certificate|inspection report|third party test|laboratory test",
       "परीक्षण रिपोर्ट|प्रकार परीक्षण|परीक्षण प्रमाण पत्र|एनएबीएल|प्रयोगशाला परीक्षण|जांच रिपोर्ट|टेस्ट रिपोर्ट",
       "test report|parikshan report"),
    _i("bis", "quality", "BIS / ISI Licence or Certification (CRS)", "बीआईएस / आईएसआई लाइसेंस",
       "bis|isi mark|bis licence|bis license|bis certificate|bis registration|crs registration|isi certificate|bureau of indian standards|isi",
       "भारतीय मानक ब्यूरो|बीआईएस|आईएसआई|आईएसआई मार्क|बीआईएस लाइसेंस",
       "bis certificate|isi mark"),
    _i("iso", "quality", "ISO Certification (ISO 9001 / 14001 / 45001)", "आईएसओ प्रमाणन (ISO 9001 / 14001 / 45001)",
       "iso|iso 9001|iso 14001|iso 45001|iso certificate|iso certification|quality management system certificate|qms certificate|ohsas|iso 27001|iso 9001 2015",
       "आईएसओ|आईएसओ प्रमाणपत्र|आईएसओ प्रमाणन|आईएसओ प्रमाण पत्र|गुणवत्ता प्रबंधन प्रणाली",
       "iso praman patra"),
    _i("methodology", "technical", "Methodology / Work Plan / Quality Assurance Plan", "कार्यप्रणाली / कार्य योजना / गुणवत्ता आश्वासन योजना",
       "methodology|work plan|work programme|work program|quality assurance plan|qap|quality plan|execution plan|project plan|implementation plan|"
       "approach and methodology|technical approach|time schedule|bar chart|pert chart|construction schedule",
       "कार्यप्रणाली|कार्य योजना|गुणवत्ता आश्वासन योजना|कार्यान्वयन योजना|पद्धति|कार्य पद्धति|समय सारणी",
       "karya yojana|karyapranali"),
    _i("service_support", "technical", "Service Centre / After-Sales Support Details", "सेवा केंद्र / विक्रय पश्चात सेवा का विवरण",
       "service centre|service center|after sales|after sales service|aftersales|service support|service engineer|support centre|local office|"
       "warranty support|service network|customer support|after sales support",
       "सेवा केंद्र|विक्रय पश्चात सेवा|बिक्री उपरांत सेवा|सर्विस सेंटर|सहायता केंद्र|बिक्री पश्चात सेवा",
       "service center|service kendra"),
    _i("warranty", "technical", "Warranty / Guarantee Undertaking", "वारंटी / गारंटी वचन पत्र",
       "warranty|warranty certificate|warranty undertaking|guarantee certificate|comprehensive warranty|warranty period|extended warranty|warranty and guarantee",
       "वारंटी|गारंटी प्रमाण पत्र|वारंटी प्रमाण पत्र|गारंटी अवधि|वारंटी वचन पत्र|वारंटी अवधि",
       "warranty praman patra"),

    # ------------------------------------------------------------ declarations & forms
    _i("blacklist", "declaration", "Non-Blacklisting / Non-Debarment Declaration", "काली सूची में न होने / अयोग्य न होने की घोषणा",
       "blacklist|blacklisted|black listed|black listing|blacklisting|non blacklisting|not blacklisted|debarred|debarment|not been blacklisted|"
       "holiday listing|non debarment|declaration regarding blacklisting|declaration regarding debarment",
       "काली सूची|ब्लैकलिस्ट|ब्लैकलिस्टेड|प्रतिबंधित|डिबार|काली सूची में नहीं|अयोग्य घोषित",
       "kali suchi|black list"),
    _i("integrity_pact", "declaration", "Integrity Pact", "सत्यनिष्ठा समझौता / इंटेग्रिटी पैक्ट",
       "integrity pact|integrity agreement|integrity pact agreement",
       "सत्यनिष्ठा संधि|इंटेग्रिटी पैक्ट|सत्यनिष्ठा समझौता|सत्यनिष्ठा करार",
       "integrity pact"),
    _i("affidavit", "declaration", "Affidavit / Self Declaration / Undertaking (on stamp paper)",
       "शपथ पत्र / स्व-घोषणा / वचन पत्र (स्टाम्प पेपर पर)",
       "affidavit|self declaration|sworn affidavit|notarized affidavit|notarised affidavit|undertaking letter|letter of undertaking|"
       "undertaking on stamp paper|declaration on stamp paper|stamp paper|notarized|notarised|notary",
       "शपथ पत्र|शपथपत्र|स्व घोषणा|स्वघोषणा|घोषणा पत्र|घोषणापत्र|वचन पत्र|वचनपत्र|उपक्रम पत्र|हलफनामा|स्टाम्प पेपर|नोटरी|स्वयं घोषणा",
       "shapath patra|shapathpatra|ghoshna patra|swa ghoshna|halfnama|vachan patra",
       w="undertaking|declaration|self certificate|self certification"),
    _i("signed_tender", "declaration", "Signed & Stamped Tender Document / Corrigendum Acceptance",
       "हस्ताक्षरित एवं मुहरबंद निविदा दस्तावेज़ / शुद्धिपत्र स्वीकृति",
       "signed tender document|signed and stamped|signed copy of tender|tender acceptance|acceptance of terms and conditions|"
       "acceptance of tender conditions|tender acceptance letter|signed corrigendum|corrigendum acknowledgement|acceptance of corrigendum|"
       "signed and sealed|terms and conditions acceptance|acceptance letter|bid acceptance|signed and stamped tender",
       "हस्ताक्षरित निविदा|निविदा स्वीकृति|शर्तों की स्वीकृति|शुद्धिपत्र पर हस्ताक्षर|मुहर एवं हस्ताक्षर|नियम एवं शर्तों की स्वीकृति|हस्ताक्षरित एवं मुहरबंद",
       "tender acceptance|signed tender"),
    _i("covering_letter", "declaration", "Covering Letter / Bid Submission Letter", "आवरण पत्र / बिड प्रस्तुति पत्र",
       "covering letter|cover letter|forwarding letter|bid submission letter|letter of bid|bid forwarding letter|submission letter|"
       "application letter|letter of submission|bid letter|tender submission form|offer letter|bid form",
       "आवरण पत्र|कवरिंग लेटर|प्रेषण पत्र|बिड प्रस्तुति पत्र|निविदा प्रस्तुति पत्र|अग्रेषण पत्र|आवेदन पत्र",
       "covering letter|avaran patra"),
    _i("checklist", "declaration", "Eligibility Compliance Statement / Document Checklist", "पात्रता अनुपालन विवरण / दस्तावेज़ चेकलिस्ट",
       "checklist|compliance checklist|eligibility compliance|eligibility criteria compliance|pre qualification compliance|documents checklist|"
       "bid checklist|check list|document checklist|eligibility checklist",
       "चेकलिस्ट|जांच सूची|पात्रता अनुपालन|पात्रता मानदंड अनुपालन|दस्तावेज चेकलिस्ट|दस्तावेजों की जांच सूची",
       "check list|checklist"),

    # ------------------------------------------------------------ misc legal / identity
    _i("address_proof", "legal", "Address Proof / Office Premises Proof", "पते का प्रमाण / कार्यालय परिसर का प्रमाण",
       "address proof|proof of address|office address proof|electricity bill|rent agreement|lease deed|utility bill|ownership proof|place of business|office premises",
       "पते का प्रमाण|पता प्रमाण|बिजली बिल|किराया अनुबंध|पट्टा विलेख|कार्यालय प्रमाण|व्यावसायिक पता|पते का सबूत|कार्यालय का पता",
       "pata praman|address praman"),
    _i("kyc_id", "legal", "Proprietor / Partner / Director ID Proof (Aadhaar / KYC)", "स्वामी / भागीदार / निदेशक पहचान प्रमाण (आधार / KYC)",
       "aadhaar|aadhar|adhar|id proof|identity proof|kyc|voter id|passport|driving licence|driving license|director identification number|din|photo id",
       "आधार|आधार कार्ड|पहचान प्रमाण|पहचान पत्र|मतदाता पहचान पत्र|केवाईसी|निदेशक पहचान संख्या|आधार संख्या",
       "aadhar card|aadhaar card|pehchan patra"),
    _i("jv", "legal", "Joint Venture / Consortium Agreement", "संयुक्त उद्यम / कंसोर्टियम समझौता",
       "joint venture|jv agreement|consortium|consortium agreement|jv|joint venture agreement|jv partner|consortium member",
       "संयुक्त उद्यम|कंसोर्टियम|संयुक्त उपक्रम|संयुक्त उद्यम समझौता",
       "sanyukt udyam|joint venture"),

    # ------------------------------------------------------------ resources
    _i("manpower", "resources", "Manpower / Key Personnel Details & CVs", "जनशक्ति / प्रमुख कर्मियों का विवरण एवं बायोडाटा",
       "manpower|man power|key personnel|technical staff|staff details|qualified engineer|engineer details|cv|curriculum vitae|resume|"
       "organisation chart|organization chart|technical personnel|list of employees|employee list|team details|technical manpower|qualification certificates",
       "जनशक्ति|मानव संसाधन|प्रमुख कर्मी|तकनीकी कर्मचारी|कर्मचारियों की सूची|बायोडाटा|अभियंता विवरण|सीवी|तकनीकी स्टाफ|प्रमुख कार्मिक",
       "manpower details|karmchari suchi"),
    _i("equipment", "resources", "Equipment / Machinery / Infrastructure Details", "उपकरण / मशीनरी / आधारभूत संरचना का विवरण",
       "equipment list|list of equipment|machinery|plant and machinery|tools and plants|infrastructure details|testing equipment|availability of equipment|"
       "owned equipment|equipment details|tools and tackles|infrastructure facilities|list of machinery",
       "उपकरण सूची|मशीनरी|संयंत्र एवं मशीनरी|आधारभूत संरचना|औजार|उपकरणों का विवरण|उपकरणों की सूची|मशीनों की सूची",
       "upkaran suchi|equipment suchi"),
    _i("site_visit", "resources", "Site Visit Certificate", "स्थल निरीक्षण प्रमाण पत्र",
       "site visit|site visit certificate|site inspection certificate|visited the site|site verification|site inspection",
       "स्थल भ्रमण|स्थल निरीक्षण|साइट विजिट|साइट निरीक्षण प्रमाण पत्र|स्थल निरीक्षण प्रमाण पत्र",
       "site visit certificate|sthal nirikshan"),
]

CATALOG: dict[str, CatalogItem] = {it.id: it for it in _ITEMS}
CATALOG_ORDER: list[str] = [it.id for it in _ITEMS]
