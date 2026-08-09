from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Any


@dataclass(frozen=True)
class BitcoinMasterState:
    timestamp:Any;btc_price:float;value_state:str;value_score:float;cycle:str;regime:str;regime_stability:str;rare_buy:str;buy_candidate:str;buy_completion:float;rare_sell:str;sell_candidate:str;sell_completion:float;distribution:str;timing:str;timing_score:float;risk:str;risk_7d:float;risk_30d:float;risk_90d:float;drawdown:float;drawdown_percentile:float;recovery_state:str;weekly_rsi:float|None;monthly_rsi:float|None;rsi_365d:float|None;daily_bollinger:str;weekly_bollinger:str;monthly_bollinger:str;nearest_support:dict|None;nearest_resistance:dict|None;buy_zones:list;sell_zones:list;onchain_state:str;derivatives_state:str;macro_state:str;etf_state:str;news_state:str;evidence:dict;confluence:dict;data_quality:dict;uncertainty:dict;factor_registry:list;historical_entry_quality_score:float|None;historical_entry_quality_state:str;entry_archetype:str;historical_entry_matched_factors:list;historical_entry_missing_factors:list;historical_entry_contradictions:list;closest_entry_episodes:list;historical_mae_median:float|None;historical_mae_best:float|None;historical_mae_worst:float|None;price_vs_200d_pct:float|None;price_vs_200w_pct:float|None;historical_entry_research_status:str
    def to_dict(self):return asdict(self)


@dataclass(frozen=True)
class BitcoinMasterDecision:
    long_term_action:str;new_entry_action:str;existing_position_action:str;risk_action:str;production_signal:str;candidate_signal:str;confidence:str;positive_drivers:list;negative_drivers:list;uncertain_drivers:list;waiting_for:list;upgrade_conditions:list;downgrade_conditions:list;invalidation:list;model_disagreement:dict;execution:str="DISABLED"
    def to_dict(self):return asdict(self)
