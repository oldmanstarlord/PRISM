export function getIndustryMacroProfile(industry?: string): {
  icon: string;
  headline: string;
  macroDrivers: string[];
  shockTransmission: string;
} {
  const norm = (industry || "").toLowerCase();
  if (norm.includes("tech") || norm.includes("information")) {
    return {
      icon: "",
      headline: "Global Enterprise IT Budgets & Currency Exposure",
      macroDrivers: [
        "Over 70% of enterprise revenues originate from North American and European corporate clients (especially BFSI and Retail).",
        "USD/INR exchange rate movements directly influence operating margins and cross-border billing realization.",
        "Global interest rate cycles and enterprise digital transformation / AI capex cycles dictate contract order flow synchronously.",
      ],
      shockTransmission:
        "When US/EU corporate IT budgets contract or FX shifts abruptly, valuation multiples across tech stocks compress in unison (high intra-sector co-movement).",
    };
  }
  if (norm.includes("financ") || norm.includes("bank") || norm.includes("insur")) {
    return {
      icon: "",
      headline: "Monetary Policy Transmission & Domestic Credit Cycle",
      macroDrivers: [
        "Reserve Bank of India (RBI) repo rate decisions directly dictate bank Net Interest Margins (NIM) and NBFC cost of funds.",
        "Systemic credit growth, deposit mobilization competition, and retail/SME delinquency cycles affect all lenders simultaneously.",
        "Foreign Institutional Investors (FIIs) trade high-liquidity financial stocks as the primary liquid proxy for India's macroeconomic GDP trajectory.",
      ],
      shockTransmission:
        "Financial institutions act as central capital arteries; stress or liquidity shocks in the banking corridor cascade into capital goods, auto financing, and real estate.",
    };
  }
  if (norm.includes("auto")) {
    return {
      icon: "",
      headline: "Retail Financing Conditions & Input Commodity Inflation",
      macroDrivers: [
        "Retail vehicle purchase volumes heavily depend on bank/NBFC vehicle financing rates and consumer credit availability.",
        "Input costs are tied directly to industrial commodities: automotive-grade sheet steel, aluminum, and rubber prices.",
        "Rural agricultural income (for 2-wheelers and tractors) alongside urban replacement demand cycles dictate sales seasonality.",
      ],
      shockTransmission:
        "Automakers connect closely with metal producers (input cost supply chain) and retail financiers (demand credit channel).",
    };
  }
  if (norm.includes("capital goods") || norm.includes("construction") || norm.includes("industrial")) {
    return {
      icon: "",
      headline: "Public Infrastructure Outlays & Private Capex Cycle",
      macroDrivers: [
        "Central and State government capital expenditure budgets for roads, railways, energy transition, and urban mobility.",
        "Private sector manufacturing capacity utilization rates determining new plant and equipment expansion cycles.",
        "Long gestation contract execution timelines, raw material escalation clauses, and working capital financing costs.",
      ],
      shockTransmission:
        "Capital Goods stocks act as economic barometers, transmitting industrial momentum between raw materials (metals/energy) and financing hubs.",
    };
  }
  if (norm.includes("oil") || norm.includes("gas") || norm.includes("fuel") || norm.includes("energy")) {
    return {
      icon: "",
      headline: "Global Crude Benchmarks & Refining Crack Spreads",
      macroDrivers: [
        "International Brent crude price benchmarks and Singapore Gross Refining Margins (GRM) dictate upstream and downstream profitability.",
        "Domestic government excise duty adjustments, windfall profit taxes, and retail auto-fuel pricing policies.",
        "Global LNG supply-demand balances and shipping freight tariffs for imported hydrocarbon feedstocks.",
      ],
      shockTransmission:
        "Oil & Gas giants represent systemic market weight; oil price swings transmit inflationary shocks across transport, chemicals, and consumer goods.",
    };
  }
  if (norm.includes("metal") || norm.includes("mining")) {
    return {
      icon: "",
      headline: "LME Global Commodity Pricing & Chinese Industrial Demand",
      macroDrivers: [
        "London Metal Exchange (LME) spot prices and Chinese manufacturing purchasing managers' indices (PMI) dictate domestic realization prices.",
        "Imported coking coal and domestic iron ore pricing parity create operating cost swings.",
        "Domestic construction, automotive, and infrastructure demand provide baseline volume consumption.",
      ],
      shockTransmission:
        "Metals stocks exhibit cyclical beta; shifts in global commodity demand rapidly feed into construction materials and industrial manufacturing.",
    };
  }
  if (norm.includes("health") || norm.includes("pharma")) {
    return {
      icon: "",
      headline: "US FDA Regulatory Oversight & Generic Pricing Dynamics",
      macroDrivers: [
        "Regulatory compliance, inspection outcomes, and Form 483 issuance by the US FDA for export-oriented manufacturing plants.",
        "Price erosion in the US generic pharmaceuticals market versus high-margin complex injectables and biosimilar pipelines.",
        "Resilient, non-cyclical growth in domestic Indian formulations driven by chronic therapy prescription adoption.",
      ],
      shockTransmission:
        "Pharma operates with defensive, lower correlation to domestic interest rate cycles, frequently acting as a portfolio hedge during cyclical drawdowns.",
    };
  }
  if (norm.includes("consumer goods") || norm.includes("fmcg") || norm.includes("durables")) {
    return {
      icon: "",
      headline: "Agricultural Monsoon Distribution & Household Purchasing Power",
      macroDrivers: [
        "Southwest monsoon spatial distribution directly drives rural farm income and staple consumer goods volume off-take.",
        "Agricultural raw material price volatility (crude palm oil, wheat, sugar, packaging materials) dictating gross margins.",
        "Urban premiumization trends versus mass rural volume recovery determining top-line growth trajectory.",
      ],
      shockTransmission:
        "FMCG stocks exhibit lower systemic beta; they serve as structural anchors in the MST with strong intra-sector coherence.",
    };
  }
  if (norm.includes("power") || norm.includes("utilit")) {
    return {
      icon: "",
      headline: "Grid Peak Load Demand & DISCOM Health",
      macroDrivers: [
        "National peak power demand driven by industrial electrification, seasonal heatwaves, and air conditioning penetration.",
        "Power Purchase Agreement (PPA) realization rates, coal linkage availability, and renewable capacity deployment.",
        "State distribution company (DISCOM) financial solvency and timely payment settlements under central schemes.",
      ],
      shockTransmission:
        "Power stocks connect heavy industry to public utilities, anchoring industrial energy demand in the empirical network.",
    };
  }
  if (norm.includes("realt")) {
    return {
      icon: "",
      headline: "Mortgage Rates, Land Acquisition & Residential Absorption",
      macroDrivers: [
        "Retail home loan interest rates and banking liquidity driving residential presales velocity.",
        "Urban land parcel acquisitions, regulatory approvals (RERA), and construction milestone completion rates.",
        "Consolidation toward organized, tier-1 branded developers with strong balance sheets.",
      ],
      shockTransmission:
        "Realty co-moves closely with banking and housing finance NBFCs, forming a sensitive interest-rate transmission corridor.",
    };
  }
  if (norm.includes("telecom")) {
    return {
      icon: "",
      headline: "Industry ARPU Trajectory & 5G Infrastructure Monetization",
      macroDrivers: [
        "Average Revenue Per User (ARPU) headline tariff increase cycles across the 3-player private oligopoly.",
        "Capital expenditure amortization for 5G network rollout, fiber backhaul, and spectrum auction liabilities.",
        "Data consumption growth per subscriber and enterprise cloud connectivity services.",
      ],
      shockTransmission:
        "Telecom connects capital-intensive infrastructure with digital consumer services, serving as an independent digital conduit.",
    };
  }
  if (norm.includes("chemic")) {
    return {
      icon: "",
      headline: "Petrochemical Feedstocks & Global Supply Chain Diversification",
      macroDrivers: [
        "Global chemical cycle demand, particularly European and American agrochemical and specialty chemical destocking.",
        "Crude oil and natural gas derivative feedstock costs dictating intermediate chemical manufacturing margins.",
        "Global 'China + 1' manufacturing diversification contracts and domestic import substitution incentives.",
      ],
      shockTransmission:
        "Chemicals link energy refining inputs to pharmaceutical, agrochemical, and automotive applications.",
    };
  }

  return {
    icon: "",
    headline: "Sector Operational Dynamics & Macro Sensitivities",
    macroDrivers: [
      `Companies in ${industry || "this sector"} share direct sensitivity to domestic GDP growth rates, inflation, and sovereign yield curves.`,
      "Co-movement is driven by synchronized demand conditions, capital access, and collective institutional investor asset allocation baskets.",
      "Regulatory frameworks and tax structures impacting this industry create synchronous valuation adjustments across peers.",
    ],
    shockTransmission:
      "Shocks in this industry propagate across empirical spanning tree edges to closely correlated supplier, customer, and financing nodes.",
  };
}
