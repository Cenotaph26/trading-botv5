#!/usr/bin/env python3
"""AI Trading Bot v5.0 — Elite Dashboard - Enhanced with Risk Management"""

import random, time, json, threading, requests, math, os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── RISK MANAGEMENT & PERFORMANCE MODULES ──────────────────
try:
    from trading_bot_improvements import (
        BacktestEngine,
        RiskManager,
        StrategyOptimizer,
        PerformanceMetrics,
        Trade,
        BacktestResult
    )
    IMPROVEMENTS_ENABLED = True
    print("✅ Risk Management modülü yüklendi")
except ImportError as e:
    print(f"⚠️  Risk Management modülü yüklenemedi: {e}")
    print("   Bot temel modda çalışacak. Gelişmiş özellikler devre dışı.")
    IMPROVEMENTS_ENABLED = False

# ── BINANCE CLIENT ─────────────────────────────────────────
class BinanceClient:
    BASE = "https://fapi.binance.com"
    def __init__(self):
        self.symbols=[]; self.ticker={}; self.prices={}
        self._klines_cache={}; self._cache_ts={}
        self.session = requests.Session()
        # Proxy kullan (geo-block bypass)
        self.proxies = None  # Railway'de proxy gerekirse buraya ekleriz
        self._fetch_symbols(); self._fetch_tickers()

    def _fetch_symbols(self):
        try:
            # Try main endpoint first
            r=self.session.get(f"{self.BASE}/fapi/v1/exchangeInfo",timeout=15,proxies=self.proxies)
            
            # If geo-blocked, try alternative public endpoint
            if r.status_code==451:
                print("Main API geo-blocked, trying alternative...")
                r=self.session.get("https://fapi.binance.com/fapi/v1/exchangeInfo",timeout=15)
            
            data=r.json()
            
            if not isinstance(data,dict) or 'symbols' not in data:
                print(f"symbols error: invalid response - using fallback minimal list")
                self.symbols=['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','MATICUSDT','AVAXUSDT','LINKUSDT']
                return
            
            # Get ALL USDT perpetual futures
            valid=[s['symbol'] for s in data['symbols']
                   if isinstance(s,dict) and s.get('symbol','').endswith('USDT')
                   and s.get('contractType')=='PERPETUAL'
                   and s.get('status')=='TRADING']
            
            self.symbols=sorted(valid)
            print(f"✓ {len(self.symbols)} pairs loaded (LIVE BINANCE DATA)")
        except Exception as e:
            print(f"symbols error: {e} - using minimal fallback")
            self.symbols=['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','MATICUSDT','AVAXUSDT','LINKUSDT']

    def _fetch_tickers(self):
        if not self.symbols:
            print("ticker error: no symbols loaded")
            return
        try:
            r=self.session.get(f"{self.BASE}/fapi/v1/ticker/24hr",timeout=15,proxies=self.proxies)
            data=r.json()
            
            if not isinstance(data,list):
                print(f"ticker error: expected list, got {type(data)}")
                return
            
            for t in data:
                if not isinstance(t,dict): continue
                s=t.get('symbol')
                if not s or s not in self.symbols: continue
                try:
                    self.ticker[s]={
                        'price':float(t.get('lastPrice',0)),
                        'change':float(t.get('priceChangePercent',0)),
                        'volume':float(t.get('volume',0)),
                        'high':float(t.get('highPrice',0)),
                        'low':float(t.get('lowPrice',0)),
                        'quoteVolume':float(t.get('quoteVolume',0)),
                        'openPrice':float(t.get('openPrice',0)),
                        'count':int(t.get('count',0)),
                    }
                    self.prices[s]=float(t.get('lastPrice',0))
                except (ValueError,TypeError): continue
            print(f"✓ {len(self.ticker)} live prices loaded")
        except Exception as e:
            print(f"ticker error: {e}")
            if not isinstance(data, list):
                print(f"ticker error: unexpected response type - {type(data)}")
                # Fallback: simulated data for development
                for s in self.symbols[:10]:
                    self.ticker[s]={'price':100.0,'change':0.5,'volume':1000,'high':105,'low':95,'quoteVolume':100000,'openPrice':99,'count':100}
                    self.prices[s]=100.0
                print(f"ok {len(self.ticker)} prices loaded (fallback)")
                return
            for t in data:
                if not isinstance(t, dict):
                    continue
                s=t.get('symbol')
                if not s or s not in self.symbols:
                    continue
                try:
                    self.ticker[s]={
                        'price':float(t.get('lastPrice',0)),
                        'change':float(t.get('priceChangePercent',0)),
                        'volume':float(t.get('volume',0)),
                        'high':float(t.get('highPrice',0)),
                        'low':float(t.get('lowPrice',0)),
                        'quoteVolume':float(t.get('quoteVolume',0)),
                        'openPrice':float(t.get('openPrice',0)),
                        'count':int(t.get('count',0)),
                    }
                    self.prices[s]=float(t.get('lastPrice',0))
                except (ValueError, TypeError) as e:
                    continue
            print(f"ok {len(self.ticker)} prices loaded")
        except Exception as e: print(f"ticker error: {e}")

    def refresh_prices(self):
        try:
            r=self.session.get(f"{self.BASE}/fapi/v1/ticker/price",timeout=5,proxies=self.proxies)
            for t in r.json():
                if t['symbol'] in self.symbols:
                    p=float(t['price'])
                    self.prices[t['symbol']]=p
                    if t['symbol'] in self.ticker:
                        self.ticker[t['symbol']]['price']=p
        except: pass

    def refresh_tickers(self):
        try:
            r=self.session.get(f"{self.BASE}/fapi/v1/ticker/24hr",timeout=10,proxies=self.proxies)
            data=r.json()
            if not isinstance(data,list): return
            for t in data:
                if not isinstance(t,dict): continue
                s=t.get('symbol')
                if not s or s not in self.symbols or s not in self.ticker: continue
                try:
                    self.ticker[s].update({
                        'price':float(t.get('lastPrice',0)),
                        'change':float(t.get('priceChangePercent',0)),
                        'volume':float(t.get('volume',0)),
                        'high':float(t.get('highPrice',0)),
                        'low':float(t.get('lowPrice',0)),
                        'quoteVolume':float(t.get('quoteVolume',0)),
                    })
                    self.prices[s]=float(t.get('lastPrice',0))
                except (ValueError,TypeError): continue
        except: pass

    def klines(self, symbol, interval='5m', limit=80):
        cache_key=f"{symbol}_{interval}"
        now=time.time()
        if cache_key in self._klines_cache and now-self._cache_ts.get(cache_key,0)<10:
            return self._klines_cache[cache_key]
        try:
            r=self.session.get(f"{self.BASE}/fapi/v1/klines",
                params={'symbol':symbol,'interval':interval,'limit':limit},
                timeout=10,proxies=self.proxies)
            
            if r.status_code!=200:
                print(f"Klines API error for {symbol}: status {r.status_code}")
                return self._klines_cache.get(cache_key,[])
            
            data=[{'t':k[0],'o':float(k[1]),'h':float(k[2]),
                   'l':float(k[3]),'c':float(k[4]),'v':float(k[5])}
                  for k in r.json()]
            
            if len(data)==0:
                print(f"Klines API returned empty data for {symbol}")
                return self._klines_cache.get(cache_key,[])
            
            self._klines_cache[cache_key]=data
            self._cache_ts[cache_key]=now
            return data
        except Exception as e:
            print(f"Klines fetch error for {symbol}: {e}")
            return self._klines_cache.get(cache_key,[])

    def price(self,s): return self.prices.get(s,0)
    def info(self,s): return self.ticker.get(s,{})

# ── TECHNICAL ANALYSIS ─────────────────────────────────────
class TA:
    @staticmethod
    def rsi(p,n=14):
        if len(p)<n+1: return 50
        d=[p[i]-p[i-1] for i in range(1,len(p))]
        g=[x if x>0 else 0 for x in d[-n:]]
        l=[-x if x<0 else 0 for x in d[-n:]]
        ag,al=sum(g)/n,sum(l)/n
        if al==0: return 100
        return 100-(100/(1+ag/al))

    @staticmethod
    def ema(p,n):
        if not p or len(p)<n: return p[-1] if p else 0
        m=2/(n+1); e=sum(p[-n:])/n
        for x in p[-n+1:]: e=(x-e)*m+e
        return e

    @staticmethod
    def macd(p):
        if len(p)<26: return 0,0
        e12=TA.ema(p,12); e26=TA.ema(p,26); m=e12-e26
        sig_d=[TA.ema(p[:i],12)-TA.ema(p[:i],26) for i in range(26,len(p))]
        sig=TA.ema(sig_d,9) if len(sig_d)>=9 else m*0.9
        return m,sig

    @staticmethod
    def bb(p,n=20):
        if len(p)<n: return p[-1],p[-1],p[-1]
        r=p[-n:]; mid=sum(r)/n
        std=(sum((x-mid)**2 for x in r)/n)**0.5
        return mid+2*std,mid,mid-2*std

    @staticmethod
    def atr(klines,n=14):
        if len(klines)<n+1: return 0
        trs=[]
        for i in range(1,len(klines)):
            h,l,pc=klines[i]['h'],klines[i]['l'],klines[i-1]['c']
            trs.append(max(h-l,abs(h-pc),abs(l-pc)))
        return sum(trs[-n:])/n

    @staticmethod
    def stoch(p,n=14):
        if len(p)<n: return 50
        lo=min(p[-n:]); hi=max(p[-n:])
        if hi==lo: return 50
        return (p[-1]-lo)/(hi-lo)*100

    @staticmethod
    def vwap(klines):
        if not klines: return 0
        tv=sum((k['h']+k['l']+k['c'])/3*k['v'] for k in klines)
        v=sum(k['v'] for k in klines)
        return tv/v if v>0 else 0

# ── AI AGENT ───────────────────────────────────────────────
class Agent:
    def __init__(self,bc):
        self.bc=bc
        self.balance=10000; self.start_balance=10000; self.peak_balance=10000
        self.positions={}; self.history=[]
        self.trades=0; self.wins=0
        self.total_profit=0; self.total_loss=0
        self.pnl_curve=[10000]; self.pnl_times=[datetime.now().strftime('%H:%M')]
        self.strategies={'Trend Following':1.0,'Mean Reversion':1.0,'Breakout':1.0,'Scalping':1.0,'VWAP Bounce':1.0}
        self.strat_trades={s:{'wins':0,'total':0} for s in self.strategies}
        self._last_analyzed={}
        self.risk={
            'max_positions':7,'position_size_pct':9,'leverage':0,
            'tp_pct':2.0,'sl_pct':0.8,'min_score':4,'min_conf':50,
            'max_atr_pct':6,'scan_size':20,'scan_interval':2,
            # Dinamik Exit Ayarları
            'profit_protect':True,      # Kâr koruma aktif
            'max_pnl_drawdown':0.4,     # Max PnL'den %40 geri çekilme = çık
            'loss_recovery':True,        # Zarar toparlanma sinyali bekle
            'smart_exit_score':-2,       # Bu skorun altında kârda çık (LONG için)
        }
        
        # ── ENHANCED RISK MANAGEMENT ──────────────────────────────
        if IMPROVEMENTS_ENABLED:
            self.risk_manager = RiskManager(
                total_capital=self.balance,
                max_risk_per_trade=0.02,      # %2 max risk per trade
                max_portfolio_heat=0.10,       # %10 max total portfolio risk
                max_correlation=0.7,           # Max 0.7 correlation between positions
                max_drawdown_limit=0.20        # %20 max drawdown before stopping
            )
            self.all_trades = []  # Track all trades as Trade objects
            self.performance_update_counter = 0
            print("✅ Risk Manager başlatıldı: Max risk %2 | Portfolio heat %10 | Max DD %20")
        else:
            self.risk_manager = None
            self.all_trades = []

    def analyze(self,sym):
        try:
            kl=self.bc.klines(sym,'5m',80)
            if len(kl)<35: return None
            c=[k['c'] for k in kl]; v=[k['v'] for k in kl]; price=c[-1]
            rsi=TA.rsi(c); stoch=TA.stoch(c)
            macd,msig=TA.macd(c)
            e20,e50=TA.ema(c,20),TA.ema(c,50)
            bbu,bbm,bbl=TA.bb(c)
            atr=TA.atr(kl); vwap=TA.vwap(kl[-20:])
            avg_v=sum(v[-20:])/20; vr=v[-1]/avg_v if avg_v>0 else 1
            score=0; reasons=[]

            if rsi<23: score+=3; reasons.append(f"RSI asiri satim ({rsi:.0f})")
            elif rsi<30: score+=2; reasons.append(f"RSI satim bolgesi ({rsi:.0f})")
            elif rsi>77: score-=3; reasons.append(f"RSI asiri alim ({rsi:.0f})")
            elif rsi>70: score-=2; reasons.append(f"RSI alim bolgesi ({rsi:.0f})")
            if stoch<20: score+=1; reasons.append(f"Stoch asiri satim ({stoch:.0f})")
            elif stoch>80: score-=1; reasons.append(f"Stoch asiri alim ({stoch:.0f})")
            if macd>msig and macd>0: score+=2; reasons.append("MACD guclu yukari")
            elif macd>msig: score+=1; reasons.append("MACD yukari donuyor")
            elif macd<msig and macd<0: score-=2; reasons.append("MACD guclu asagi")
            elif macd<msig: score-=1; reasons.append("MACD asagi donuyor")
            if price>e20>e50: score+=1; reasons.append("EMA yukari trend")
            elif price<e20<e50: score-=1; reasons.append("EMA asagi trend")
            prev_c=c[-2] if len(c)>1 else price
            if prev_c<e20 and price>e20: score+=1; reasons.append("EMA20 yukari kirisi")
            elif prev_c>e20 and price<e20: score-=1; reasons.append("EMA20 asagi kirisi")
            if price<bbl: score+=2; reasons.append("Alt Bollinger kirisi")
            elif price<bbl*1.005: score+=1; reasons.append("Alt Bollinger yakin")
            elif price>bbu: score-=2; reasons.append("Ust Bollinger kirisi")
            elif price>bbu*0.995: score-=1; reasons.append("Ust Bollinger yakin")
            if price<vwap*0.998: score+=1; reasons.append("VWAP altinda")
            elif price>vwap*1.002: score-=1; reasons.append("VWAP ustunde")
            if vr>3.0: score+=2; reasons.append(f"Hacim patlamasi x{vr:.1f}")
            elif vr>2.0: score+=1; reasons.append(f"Hacim artisi x{vr:.1f}")
            body=abs(c[-1]-c[-2]) if len(c)>1 else 0
            wick=kl[-1]['h']-kl[-1]['l']
            lower_wick=min(c[-1],kl[-1]['o'])-kl[-1]['l']
            upper_wick=kl[-1]['h']-max(c[-1],kl[-1]['o'])
            if wick>0:
                if lower_wick/wick>0.6 and c[-1]>c[-2]: score+=1; reasons.append("Hammer formasyonu")
                if upper_wick/wick>0.6 and c[-1]<c[-2]: score+=1; reasons.append("Shooting star")
            atr_pct=(atr/price*100) if price>0 else 0
            if atr_pct>self.risk['max_atr_pct']: return None
            conf=min(abs(score)/8*100,97)
            return dict(sym=sym,price=price,score=score,conf=conf,
                        rsi=round(rsi,1),stoch=round(stoch,1),
                        macd=round(macd,8),msig=round(msig,8),
                        e20=round(e20,6),e50=round(e50,6),
                        bbu=round(bbu,6),bbl=round(bbl,6),
                        vwap=round(vwap,6),atr=round(atr,8),
                        atr_pct=round(atr_pct,2),vr=round(vr,2),
                        reasons=reasons,klines=kl[-50:])
        except: return None

    def decide(self,sym):
        if sym in self.positions: return None
        now=time.time()
        if now-self._last_analyzed.get(sym,0)<10: return None
        self._last_analyzed[sym]=now
        a=self.analyze(sym)
        if not a: return None
        
        # ENHANCED ENTRY FILTERS - Sadece güçlü sinyallere gir
        
        # 1. Minimum score threshold - Daha yüksek
        if a['score']>=self.risk['min_score']: action='LONG'
        elif a['score']<=-self.risk['min_score']: action='SHORT'
        else: return None
        
        # 2. Confidence çok düşükse REDDET
        if a['conf']<self.risk['min_conf']: return None
        
        # 3. Volume çok düşükse REDDET (pump-dump önleme)
        if a['vr']<0.5:
            print(f"{sym}: Volume cok dusuk (VR:{a['vr']:.1f}) - atla")
            return None
        
        # 4. ATR çok yüksekse REDDET (volatilite riski)
        if a['atr_pct']>self.risk['max_atr_pct']:
            print(f"{sym}: ATR cok yuksek ({a['atr_pct']:.2f}%) - atla")
            return None
        
        # 5. RSI EXTREME ZONES - Aşırı bölgede giriş yapma
        if action=='LONG' and a['rsi']>75:
            print(f"{sym}: RSI asiri yuksek ({a['rsi']}) - overbought, atla")
            return None
        if action=='SHORT' and a['rsi']<25:
            print(f"{sym}: RSI asiri dusuk ({a['rsi']}) - oversold, atla")
            return None
        
        # 6. Momentum confirmation - Birden fazla indicator onaylamalı
        confirmations=0
        
        # RSI confirms trend
        if action=='LONG' and 40<a['rsi']<70: confirmations+=1
        if action=='SHORT' and 30<a['rsi']<60: confirmations+=1
        
        # MACD confirms
        if action=='LONG' and a['macd']>0: confirmations+=1
        if action=='SHORT' and a['macd']<0: confirmations+=1
        
        # Stochastic confirms
        if action=='LONG' and a['stoch']>20: confirmations+=1
        if action=='SHORT' and a['stoch']<80: confirmations+=1
        
        # Need at least 2 confirmations
        if confirmations<2:
            print(f"{sym}: Yetersiz onay ({confirmations}/3) - atla")
            return None
        
        # 7. Fiyat Bollinger bandın ortasında mı? (çok uçlarda girme)
        bb_mid=(a['bbu']+a['bbl'])/2
        price_pos=(a['price']-a['bbl'])/(a['bbu']-a['bbl']) if a['bbu']>a['bbl'] else 0.5
        
        if action=='LONG' and price_pos>0.95:
            print(f"{sym}: Fiyat BB ustunde ({price_pos:.0%}) - atla")
            return None
        if action=='SHORT' and price_pos<0.05:
            print(f"{sym}: Fiyat BB altinda ({price_pos:.0%}) - atla")
            return None
        
        strat=self._pick_strat()
        lev=random.choice([2,3,5,10]) if self.risk['leverage']==0 else self.risk['leverage']
        
        return dict(action=action,sym=sym,price=a['price'],conf=a['conf'],
                    reasons=a['reasons'],strat=strat,lev=lev,atr=a['atr'],score=a['score'],
                    ind=dict(rsi=a['rsi'],stoch=a['stoch'],macd=a['macd'],e20=a['e20'],
                             e50=a['e50'],bbu=a['bbu'],bbl=a['bbl'],vwap=a['vwap'],
                             vr=a['vr'],atr_pct=a['atr_pct']),
                    klines=a['klines'])

    def _pick_strat(self):
        # Ensure all strategies get chances - boost unused ones
        for s in self.strategies:
            if self.strat_trades[s]['total'] == 0:
                self.strategies[s] = max(self.strategies[s], 1.0)  # Minimum score
        
        t=sum(self.strategies.values()); r=random.uniform(0,t); c=0
        for s,v in self.strategies.items():
            c+=v
            if r<=c: return s
        return 'Trend Following'

    def open(self,d):
        p,lev=d['price'],d['lev']
        
        # ── ENHANCED POSITION SIZING ──────────────────────────────
        if IMPROVEMENTS_ENABLED and self.risk_manager:
            # Calculate stop loss price
            sl_m=self.risk['sl_pct']/100*(lev/3)
            if d['action']=='LONG': 
                sl_price=p*(1-sl_m)
            else: 
                sl_price=p*(1+sl_m)
            
            # Get historical performance for Kelly Criterion
            if len(self.all_trades) > 10:
                recent_trades = self.all_trades[-50:]
                winning = [t for t in recent_trades if t.pnl > 0]
                losing = [t for t in recent_trades if t.pnl <= 0]
                
                win_rate = len(winning) / len(recent_trades) if recent_trades else 0.5
                avg_win = sum(t.pnl for t in winning) / len(winning) if winning else 0
                avg_loss = abs(sum(t.pnl for t in losing) / len(losing)) if losing else 0
                
                # Risk-adjusted position sizing
                position_data = self.risk_manager.calculate_position_size(
                    entry_price=p,
                    stop_loss_price=sl_price,
                    leverage=lev,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss
                )
            else:
                # Not enough data - use fixed risk
                position_data = self.risk_manager.calculate_position_size(
                    entry_price=p,
                    stop_loss_price=sl_price,
                    leverage=lev
                )
            
            # Check portfolio constraints
            portfolio_heat = self.risk_manager.calculate_portfolio_heat()
            should_stop, stop_reason = self.risk_manager.should_stop_trading()
            
            if should_stop:
                print(f"⚠️  {d['sym']}: Trading stopped - {stop_reason}")
                return
            
            if portfolio_heat > 0.08:  # 8% portfolio heat
                print(f"⚠️  {d['sym']}: Portfolio heat too high ({portfolio_heat:.1%})")
                return
            
            # Use risk-adjusted size
            sz = position_data['size_usd']
            print(f"📊 {d['sym']}: Position ${sz:,.0f} ({position_data['size_pct']:.1f}%) | Risk ${position_data['risk_amount']:.2f} | Method: {position_data['method']}")
        else:
            # Original fixed percentage sizing
            sz=self.balance*(self.risk['position_size_pct']/100)
        
        # Calculate TP/SL
        tp_m=self.risk['tp_pct']/100*(lev/3)
        sl_m=self.risk['sl_pct']/100*(lev/3)
        if d['action']=='LONG': tp=p*(1+tp_m); sl=p*(1-sl_m)
        else: tp=p*(1-tp_m); sl=p*(1+sl_m)
        
        # Open position
        self.positions[d['sym']]=dict(
            type=d['action'],entry=p,cur=p,tp=tp,sl=sl,sz=sz,lev=lev,
            pnl=0,pnl_pct=0,strat=d['strat'],reasons=d['reasons'],ind=d['ind'],
            klines=d.get('klines',[]),t0=datetime.now().isoformat(),
            conf=d['conf'],score=d['score'],max_pnl=0,min_pnl=0,ticks=0)
        
        # Register with risk manager
        if IMPROVEMENTS_ENABLED and self.risk_manager:
            self.risk_manager.add_position(
                symbol=d['sym'],
                size=sz,
                entry_price=p,
                stop_loss=sl,
                leverage=lev
            )

    def update(self):
        close=[]
        for sym,pos in self.positions.items():
            try:
                p=self.bc.price(sym)
                if p==0: continue
                pos['cur']=p; pos['ticks']+=1; m=pos['lev']
                if pos['type']=='LONG': pct=(p-pos['entry'])/pos['entry']*100*m
                else: pct=(pos['entry']-p)/pos['entry']*100*m
                pnl=pos['sz']*pct/100
                pos['pnl']=pnl; pos['pnl_pct']=pct
                pos['max_pnl']=max(pos['max_pnl'],pnl); pos['min_pnl']=min(pos['min_pnl'],pnl)
                
                # Force fresh klines every update
                cache_key=f"{sym}_5m"
                self.bc._cache_ts[cache_key]=0
                new_kl=self.bc.klines(sym,'5m',50)
                if new_kl and len(new_kl)>0:
                    pos['klines']=new_kl
                    if pos['ticks']%5==0:
                        print(f"Updated {sym} klines: {len(new_kl)} candles, last close: ${new_kl[-1]['c']:.6f}")
                else:
                    print(f"WARNING: {sym} klines fetch failed or empty")
                
                # DYNAMIC EXIT LOGIC - Akıllı Çıkış Sistemi
                tp_distance_pct=abs(pos['tp']-p)/p*100
                sl_distance_pct=abs(p-pos['sl'])/p*100
                
                # 1. PROFIT PROTECTION - Karda ise momentum kayboldu mu kontrol et
                if pnl>0 and pos['ticks']>5:  # En az 5 tick geçmiş olmalı (önceden 3'tü)
                    should_exit=False
                    
                    # Re-analyze current market conditions
                    a=self.analyze(sym)
                    if a:
                        current_score=a['score']
                        
                        # Sadece GÜÇLÜ ters sinyal varsa çık (daha yüksek threshold)
                        if pos['type']=='LONG' and current_score<=-3:  # Önceden -2
                            should_exit=True
                            reason=f"Guclu ters momentum (skor:{current_score})"
                        elif pos['type']=='SHORT' and current_score>=3:  # Önceden 2
                            should_exit=True
                            reason=f"Guclu ters momentum (skor:{current_score})"
                        
                        # Max PnL'den geri çekilme threshold'ı daha yüksek
                        if pos['max_pnl']>0 and pnl<pos['max_pnl']*0.5:  # %50 geri çekilme (önceden %40)
                            should_exit=True
                            reason=f"Max PnL'den %50+ geri cekilme"
                        
                        # TP'ye çok yakınsa (<%0.5) ve momentum zayıfsa çık
                        if tp_distance_pct<0.5 and abs(current_score)<1:
                            should_exit=True
                            reason="TP'ye cok yakin - guvenli kar al"
                    
                    if should_exit:
                        close.append((sym,f"Smart Exit: {reason}"))
                        continue
                
                # 2. LOSS PREVENTION - Zarar büyümeden erken kes
                if pnl<0 and pos['ticks']>2:
                    should_exit=False
                    
                    # KRITIK: Zarar %2'yi geçtiyse direkt çık
                    if abs(pnl_pct)>2.0:
                        should_exit=True
                        reason=f"Zarar %2'yi gecti ({pnl_pct:.1f}%) - acil kes"
                    
                    # SL'ye %1.5 kaldıysa çık
                    elif sl_distance_pct<1.5:
                        should_exit=True
                        reason="SL'ye cok yakin - erken kes"
                    
                    # Zarar %1.5'i geçtiyse ve toparlanma sinyali yoksa çık
                    elif abs(pnl_pct)>1.5:
                        a=self.analyze(sym)
                        if a:
                            current_score=a['score']
                            # Toparlanma sinyali yok - çık
                            if pos['type']=='LONG' and current_score<2:
                                should_exit=True
                                reason=f"Zarar buyuyor, toparlanma yok (skor:{current_score})"
                            elif pos['type']=='SHORT' and current_score>-2:
                                should_exit=True
                                reason=f"Zarar buyuyor, toparlanma yok (skor:{current_score})"
                    
                    if should_exit:
                        close.append((sym,f"Loss Cut: {reason}"))
                        continue
                
                # 3. STANDARD TP/SL CHECKS
                if pos['type']=='LONG':
                    if p>=pos['tp']: close.append((sym,'TP'))
                    elif p<=pos['sl']: close.append((sym,'SL'))
                else:
                    if p<=pos['tp']: close.append((sym,'TP'))
                    elif p>=pos['sl']: close.append((sym,'SL'))
                    
            except Exception as e:
                print(f"Position update error for {sym}: {e}")
        
        for sym,why in close: self.close(sym,why)

    def close(self,sym,why='Manual'):
        if sym not in self.positions: return
        pos=self.positions[sym]
        
        # ── CALCULATE COSTS (Commission + Slippage) ──────────────
        commission = pos['sz'] * pos['lev'] * 0.0004 * 2  # Entry + Exit, Binance Futures
        slippage = pos['sz'] * 0.0005  # 0.05% average slippage
        net_pnl = pos['pnl'] - commission - slippage
        
        # Update balance
        self.balance+=net_pnl; self.peak_balance=max(self.peak_balance,self.balance)
        self.trades+=1; won=net_pnl>0
        if won: self.wins+=1; self.total_profit+=net_pnl
        else: self.total_loss+=abs(net_pnl)
        
        # Update strategy scores
        s=pos['strat']
        self.strategies[s]=min(3.0,self.strategies[s]+(0.18 if won else -0.06))
        self.strategies[s]=max(0.1,self.strategies[s])
        st=self.strat_trades[s]; st['total']+=1
        if won: st['wins']+=1
        
        # Calculate duration
        delta=datetime.now()-datetime.fromisoformat(pos['t0']); secs=delta.total_seconds()
        ht=f"{int(secs)}s" if secs<60 else f"{int(secs/60)}m" if secs<3600 else f"{int(secs/3600)}h"
        
        # ── ENHANCED TRADE TRACKING ──────────────────────────────
        if IMPROVEMENTS_ENABLED:
            try:
                # Create Trade object with full details
                trade_obj = Trade(
                    entry_time=datetime.fromisoformat(pos['t0']),
                    exit_time=datetime.now(),
                    symbol=sym,
                    direction=pos['type'],
                    entry_price=pos['entry'],
                    exit_price=pos['cur'],
                    size=pos['sz'],
                    leverage=pos['lev'],
                    stop_loss=pos['sl'],
                    take_profit=pos['tp'],
                    pnl=net_pnl,
                    pnl_pct=(net_pnl / pos['sz']) * 100,
                    commission=commission,
                    slippage=slippage,
                    mae=pos['min_pnl'],  # Maximum Adverse Excursion
                    mfe=pos['max_pnl'],  # Maximum Favorable Excursion
                    exit_reason=why
                )
                
                self.all_trades.append(trade_obj)
                
                # Update risk manager
                if self.risk_manager:
                    self.risk_manager.remove_position(sym)
                    self.risk_manager.total_capital = self.balance
                    self.risk_manager.update_drawdown(self.balance)
                
                # Performance update every 10 trades
                self.performance_update_counter += 1
                if self.performance_update_counter % 10 == 0:
                    self._print_performance_update()
                    
            except Exception as e:
                print(f"⚠️  Trade tracking error: {e}")
        
        # Save to history
        rec=dict(id=self.trades,sym=sym,type=pos['type'],entry=pos['entry'],exit=pos['cur'],
                 tp=pos['tp'],sl=pos['sl'],pnl=round(net_pnl,2),pnl_pct=round((net_pnl/pos['sz'])*100,2),
                 lev=pos['lev'],strat=pos['strat'],reasons=pos['reasons'],why=why,
                 time=datetime.now().strftime('%H:%M:%S'),ht=ht,won=won,
                 max_pnl=round(pos['max_pnl'],2),min_pnl=round(pos['min_pnl'],2),score=pos['score'],
                 commission=round(commission,2),slippage=round(slippage,2))
        self.history.insert(0,rec)
        if len(self.history)>200: self.history.pop()
        
        # Update PnL curve
        self.pnl_curve.append(round(self.balance,2)); self.pnl_times.append(datetime.now().strftime('%H:%M'))
        if len(self.pnl_curve)>100: self.pnl_curve.pop(0); self.pnl_times.pop(0)
        
        del self.positions[sym]
        print(f"[{'WIN' if won else 'LOSS'}] {sym} {pos['type']} | ${net_pnl:.2f} ({(net_pnl/pos['sz'])*100:.2f}%) | {why} | Costs: ${commission+slippage:.2f}")

    def wr(self): return (self.wins/self.trades*100) if self.trades>0 else 50.0
    def total_pnl(self): return round(self.balance-self.start_balance,2)
    def drawdown(self): return round((self.peak_balance-self.balance)/self.peak_balance*100,2) if self.peak_balance>0 else 0
    def profit_factor(self):
        if self.total_loss==0: return 99.9 if self.total_profit>0 else 1.0
        return round(self.total_profit/self.total_loss,2)
    
    def _print_performance_update(self):
        """Print detailed performance metrics every 10 trades"""
        if not IMPROVEMENTS_ENABLED or len(self.all_trades) < 10:
            return
        
        try:
            metrics = PerformanceMetrics(self.all_trades)
            
            # Calculate metrics
            sharpe = metrics.sharpe_ratio()
            sortino = metrics.sortino_ratio()
            exp_data = metrics.expectancy()
            streaks = metrics.calculate_streaks()
            
            # Risk-adjusted metrics
            total_return_pct = ((self.balance - self.start_balance) / self.start_balance) * 100
            max_dd_pct = self.risk_manager.current_drawdown * 100 if self.risk_manager else self.drawdown()
            risk_adj = metrics.risk_adjusted_metrics(total_return_pct, max_dd_pct)
            
            # Portfolio status
            portfolio_heat = self.risk_manager.calculate_portfolio_heat() if self.risk_manager else 0
            
            print("\n" + "="*70)
            print("📊 PERFORMANS GÜNCELLEMESİ")
            print("="*70)
            print(f"Toplam Trade:          {len(self.all_trades)}")
            print(f"Sermaye:               ${self.balance:,.2f} ({total_return_pct:+.2f}%)")
            print(f"Win Rate:              {self.wr():.1f}%")
            print(f"Profit Factor:         {self.profit_factor():.2f}")
            print(f"")
            print(f"Sharpe Ratio:          {sharpe:.2f}")
            print(f"Sortino Ratio:         {sortino:.2f}")
            print(f"Calmar Ratio:          {risk_adj['calmar_ratio']:.2f}")
            print(f"")
            print(f"Expectancy:            ${exp_data['expectancy']:.2f}")
            print(f"Expectancy Ratio:      {exp_data['expectancy_ratio']:.2f}")
            print(f"")
            print(f"Current Streak:        {streaks['current_streak']:+d}")
            print(f"Max Win Streak:        {streaks['max_win_streak']}")
            print(f"Max Loss Streak:       {streaks['max_loss_streak']}")
            print(f"")
            print(f"Performance Grade:     {risk_adj['grade']}")
            print(f"Risk Score:            {risk_adj['risk_score']}/100")
            print(f"")
            print(f"Portfolio Heat:        {portfolio_heat:.1%}")
            print(f"Current Drawdown:      {max_dd_pct:.2f}%")
            print(f"Open Positions:        {len(self.positions)}/{self.risk['max_positions']}")
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"⚠️  Performance update error: {e}")

# ── ENGINE ─────────────────────────────────────────────────
class Engine:
    def __init__(self):
        print("Binance baglaniyor...")
        self.bc=BinanceClient(); self.agent=Agent(self.bc)
        self.running=False; self.tick=0; self.events=[]; self.start_time=None

    def log(self,msg,lvl='info'):
        self.events.insert(0,{'t':datetime.now().strftime('%H:%M:%S'),'msg':msg,'lvl':lvl})
        if len(self.events)>500: self.events.pop()

    def start(self):
        self.running=True; self.start_time=datetime.now().isoformat()
        self.log("Bot baslatildi - Piyasa taranıyor...","success")
        threading.Thread(target=self._bg_prices,daemon=True).start()
        threading.Thread(target=self._bg_tickers,daemon=True).start()
        print(f"\n{'='*50}\nBot Baslatildi | ${self.agent.balance:.0f} | {len(self.bc.symbols)} cift\n{'='*50}\n")
        while self.running:
            try:
                self.agent.update()
                r=self.agent.risk
                if self.tick%r['scan_interval']==0:
                    n=min(r['scan_size'],len(self.bc.symbols))
                    syms=random.sample(self.bc.symbols,n)
                    for s in syms:
                        if len(self.agent.positions)>=r['max_positions']: break
                        d=self.agent.decide(s)
                        if d:
                            self.agent.open(d)
                            sz=self.agent.positions[s]['sz']
                            self.log(f"{s} {d['action']} | ${sz:.0f} pozisyon | {d['lev']}x | @${d['price']:.4f} | AI:{d['conf']:.0f}%","trade")
                self.tick+=1; time.sleep(2)
            except Exception as e: self.log(f"Hata: {e}","error"); time.sleep(2)

    def stop(self):
        self.running=False; self.log("Bot durduruldu","warn")

    def _bg_prices(self):
        while self.running: self.bc.refresh_prices(); time.sleep(2)
    def _bg_tickers(self):
        while self.running: self.bc.refresh_tickers(); time.sleep(15)

    def state(self):
        coins={}
        for s in self.bc.symbols:
            t=self.bc.info(s)
            if t: coins[s]=dict(price=t.get('price',0),change=round(t.get('change',0),2),
                volume=t.get('volume',0),high=t.get('high',0),low=t.get('low',0),
                quoteVolume=t.get('quoteVolume',0),count=t.get('count',0))
        pos_out={}
        for s,p in self.agent.positions.items():
            pos_out[s]=dict(type=p['type'],entry=p['entry'],cur=p['cur'],tp=p['tp'],sl=p['sl'],
                sz=p['sz'],lev=p['lev'],pnl=round(p['pnl'],2),pnl_pct=round(p['pnl_pct'],2),
                strat=p['strat'],reasons=p['reasons'],ind=p['ind'],t0=p['t0'],
                conf=p['conf'],score=p['score'],max_pnl=round(p['max_pnl'],2),
                min_pnl=round(p['min_pnl'],2),ticks=p['ticks'],klines=p['klines'][-50:])
        strat_detail={}
        for s,v in self.agent.strategies.items():
            st=self.agent.strat_trades[s]; wr=st['wins']/st['total']*100 if st['total']>0 else 0
            strat_detail[s]=dict(score=round(v,3),trades=st['total'],wr=round(wr,1))
        uptime=''
        if self.start_time:
            d=datetime.now()-datetime.fromisoformat(self.start_time)
            h,m=divmod(int(d.total_seconds()),3600); m,s=divmod(m,60); uptime=f"{h:02d}:{m:02d}:{s:02d}"
        return dict(balance=round(self.agent.balance,2),total_pnl=self.agent.total_pnl(),
            total_pnl_pct=round(self.agent.total_pnl()/self.agent.start_balance*100,2),
            trades=self.agent.trades,wins=self.agent.wins,wr=round(self.agent.wr(),1),
            active=len(self.agent.positions),drawdown=self.agent.drawdown(),
            profit_factor=self.agent.profit_factor(),positions=pos_out,
            history=self.agent.history[:60],strategies=strat_detail,coins=coins,
            running=self.running,curve=self.agent.pnl_curve,pnl_times=self.agent.pnl_times,
            events=self.events[:80],uptime=uptime,coin_count=len(self.bc.symbols),
            risk=self.agent.risk)


# ── HTML FRONTEND ──────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Trading Bot v5</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#03060e;--s1:#060c18;--s2:#0a1220;--s3:#0e1828;
  --b:#152030;--b2:#1c2d42;--b3:#243650;
  --cyan:#00e5ff;--green:#00ff94;--red:#ff2d55;
  --yellow:#ffd60a;--purple:#bf5fff;--orange:#ff7c30;--teal:#00d4aa;
  --text:#cce4f0;--dim:#4a6e8c;--dimmer:#2a4560;
  --mono:'JetBrains Mono',monospace;--dsp:'Orbitron',sans-serif;
}
body{background:var(--bg);color:var(--text);font-family:var(--mono);
  font-size:12px;min-height:100vh;overflow-x:hidden;
  background-image:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(0,229,255,0.04),transparent),
    radial-gradient(ellipse 60% 40% at 100% 60%,rgba(191,95,255,0.03),transparent);}
body::after{content:'';position:fixed;inset:0;pointer-events:none;z-index:9999;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.03) 3px,rgba(0,0,0,0.03) 4px)}
/* TICKER */
.ticker-wrap{height:30px;background:var(--s1);border-bottom:1px solid var(--b);overflow:hidden;
  display:flex;align-items:center;position:relative}
.ticker-wrap::before,.ticker-wrap::after{content:'';position:absolute;top:0;bottom:0;width:60px;z-index:2;pointer-events:none}
.ticker-wrap::before{left:0;background:linear-gradient(90deg,var(--s1),transparent)}
.ticker-wrap::after{right:0;background:linear-gradient(-90deg,var(--s1),transparent)}
.ticker-track{display:flex;animation:tickscroll 90s linear infinite;white-space:nowrap;gap:0}
.ticker-track:hover{animation-play-state:paused}
@keyframes tickscroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.tick-item{padding:0 16px;height:30px;display:inline-flex;align-items:center;gap:6px;border-right:1px solid var(--b);flex-shrink:0}
.t-sym{color:var(--cyan);font-weight:700;font-size:10px;letter-spacing:1.5px}
.t-price{color:var(--text);font-size:10px}
.t-up{color:var(--green);font-size:10px}.t-dn{color:var(--red);font-size:10px}
/* HEADER */
header{background:rgba(6,12,24,0.96);backdrop-filter:blur(20px);border-bottom:1px solid var(--b);
  padding:10px 22px;display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:30px;z-index:200}
.logo{font-family:var(--dsp);font-size:20px;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,var(--cyan) 0%,var(--teal) 50%,var(--green) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo-sub{font-size:9px;letter-spacing:3px;color:var(--dim);margin-top:1px}
.hdr-stats{display:flex;gap:24px;align-items:center}
.hs{text-align:center}
.hs-v{font-family:var(--dsp);font-size:16px;font-weight:700;letter-spacing:1px;line-height:1.1}
.hs-l{font-size:8px;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-top:1px}
.sep{width:1px;height:28px;background:var(--b2)}
.hdr-ctrl{display:flex;gap:8px;align-items:center}
.sdot{width:7px;height:7px;border-radius:50%;background:var(--dim)}
.sdot.on{background:var(--green);box-shadow:0 0 8px var(--green);animation:dp 1.5s ease infinite}
@keyframes dp{0%,100%{box-shadow:0 0 5px var(--green)}50%{box-shadow:0 0 16px var(--green),0 0 28px rgba(0,255,148,0.3)}}
.stxt{font-size:10px;letter-spacing:2px;font-weight:700}
.btn{padding:7px 16px;border:1px solid;border-radius:3px;background:none;font-family:var(--mono);
  font-size:10px;font-weight:700;letter-spacing:2px;cursor:pointer;transition:.15s;text-transform:uppercase}
.btn:active{transform:scale(.97)}.btn:disabled{opacity:.25;cursor:not-allowed}
.btn-go{border-color:var(--green);color:var(--green)}.btn-stop{border-color:var(--red);color:var(--red)}
.upt{font-size:9px;color:var(--dim);font-family:var(--dsp);letter-spacing:1px}
/* MAIN GRID */
.main{padding:10px 14px;display:grid;gap:8px;
  grid-template-columns:repeat(6,1fr);
  grid-template-areas:
    "stats stats stats stats stats stats"
    "coins coins coins coins coins coins"
    "chart chart chart strat strat strat"
    "pos pos hist hist log log"
    "risk risk risk risk risk risk"}
/* STATS */
.stats-row{grid-area:stats;display:grid;grid-template-columns:repeat(8,1fr);gap:7px}
.sc{background:var(--s1);border:1px solid var(--b);border-radius:3px;padding:10px 12px;
  position:relative;overflow:hidden;transition:.2s}
.sc:hover{border-color:var(--b3);transform:translateY(-1px)}
.sc::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px}
.sc:nth-child(1)::after{background:linear-gradient(90deg,var(--cyan),var(--teal))}
.sc:nth-child(2)::after{background:linear-gradient(90deg,var(--green),var(--teal))}
.sc:nth-child(3)::after{background:linear-gradient(90deg,var(--yellow),var(--orange))}
.sc:nth-child(4)::after{background:linear-gradient(90deg,var(--teal),var(--green))}
.sc:nth-child(5)::after{background:linear-gradient(90deg,var(--red),var(--orange))}
.sc:nth-child(6)::after{background:linear-gradient(90deg,var(--purple),var(--cyan))}
.sc:nth-child(7)::after{background:linear-gradient(90deg,var(--orange),var(--yellow))}
.sc:nth-child(8)::after{background:linear-gradient(90deg,var(--cyan),var(--purple))}
.sc-lbl{font-size:8px;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-bottom:4px}
.sc-val{font-family:var(--dsp);font-size:19px;font-weight:700;letter-spacing:1px;line-height:1}
.sc-sub{font-size:9px;color:var(--dim);margin-top:2px}
.c-cyan{color:var(--cyan)}.c-green{color:var(--green)}.c-red{color:var(--red)}
.c-yellow{color:var(--yellow)}.c-purple{color:var(--purple)}.c-teal{color:var(--teal)}.c-orange{color:var(--orange)}
/* PANEL */
.panel{background:var(--s1);border:1px solid var(--b);border-radius:3px;overflow:hidden}
.ph{padding:9px 12px;border-bottom:1px solid var(--b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,.15)}
.ph-l{display:flex;align-items:center;gap:8px}
.ph-title{font-family:var(--dsp);font-size:11px;font-weight:700;letter-spacing:2px}
.badge{padding:2px 7px;border-radius:2px;font-size:8px;font-weight:700;letter-spacing:1px;border:1px solid}
.bd-c{background:rgba(0,229,255,.07);border-color:rgba(0,229,255,.2);color:var(--cyan)}
.bd-g{background:rgba(0,255,148,.07);border-color:rgba(0,255,148,.2);color:var(--green)}
.bd-r{background:rgba(255,45,85,.07);border-color:rgba(255,45,85,.2);color:var(--red)}
.bd-y{background:rgba(255,214,10,.07);border-color:rgba(255,214,10,.2);color:var(--yellow)}
.bd-d{background:rgba(74,110,140,.07);border-color:rgba(74,110,140,.2);color:var(--dim)}
.scroll{padding:8px;max-height:450px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--b2) transparent}
.scroll::-webkit-scrollbar{width:3px}.scroll::-webkit-scrollbar-thumb{background:var(--b2)}
/* COINS */
.coins-panel{grid-area:coins}
.ctoolbar{padding:7px 10px;border-bottom:1px solid var(--b);display:flex;gap:7px;align-items:center}
.cinput{background:var(--s2);border:1px solid var(--b);border-radius:2px;padding:5px 9px;
  color:var(--text);font-family:var(--mono);font-size:10px;outline:none;width:150px}
.cinput:focus{border-color:var(--cyan)}.cinput::placeholder{color:var(--dim)}
.sb{padding:3px 9px;background:none;border:1px solid var(--b);border-radius:2px;color:var(--dim);
  font-family:var(--mono);font-size:9px;cursor:pointer;transition:.15s;letter-spacing:.5px}
.sb.active,.sb:hover{border-color:var(--cyan);color:var(--cyan)}
.cg{display:grid;grid-template-columns:repeat(auto-fill,minmax(95px,1fr));gap:4px;
  padding:7px;max-height:280px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--b2) transparent}
.cg::-webkit-scrollbar{width:3px}.cg::-webkit-scrollbar-thumb{background:var(--b2)}
.cc{background:var(--s2);border:1px solid var(--b);border-radius:2px;padding:7px 9px;
  cursor:pointer;transition:.15s;position:relative;overflow:hidden}
.cc:hover{border-color:var(--cyan);background:var(--s3);transform:translateY(-1px)}
.cc.has-pos{border-color:rgba(0,229,255,.35);background:rgba(0,229,255,.04)}
.cc.has-pos::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:var(--cyan);box-shadow:0 0 5px var(--cyan)}
.cc-n{font-weight:700;font-size:10px;letter-spacing:.5px;margin-bottom:2px}
.cc-p{font-size:9px;color:var(--dim);margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cc-c{font-size:9px;font-weight:700;padding:1px 4px;border-radius:2px;display:inline-block}
.up-ch{background:rgba(0,255,148,.1);color:var(--green)}.dn-ch{background:rgba(255,45,85,.1);color:var(--red)}
/* CHART */
.chart-panel{grid-area:chart}
.ch-tb{padding:6px 10px;border-bottom:1px solid var(--b);display:flex;gap:5px;align-items:center}
.tf-btn{padding:2px 8px;background:none;border:1px solid var(--b);border-radius:2px;color:var(--dim);
  font-family:var(--mono);font-size:9px;cursor:pointer;transition:.15s;letter-spacing:.5px}
.tf-btn.active,.tf-btn:hover{border-color:var(--cyan);color:var(--cyan)}
.mode-btn{padding:2px 8px;background:none;border:1px solid var(--b);border-radius:2px;color:var(--dim);
  font-family:var(--mono);font-size:9px;cursor:pointer;transition:.15s;letter-spacing:.5px}
.mode-btn.active{border-color:var(--yellow);color:var(--yellow)}
#cv-wrap{position:relative}
#cv{width:100%;display:block;cursor:crosshair}
#cvtt{position:absolute;background:rgba(6,12,24,0.96);border:1px solid var(--b3);border-radius:3px;
  padding:7px 9px;font-size:9px;pointer-events:none;display:none;line-height:1.9;min-width:130px;z-index:10}
.ch-info{padding:4px 10px;display:flex;gap:14px;font-size:9px;color:var(--dim);
  border-top:1px solid var(--b);background:rgba(0,0,0,.1)}
/* STRAT */
.strat-panel{grid-area:strat}
.sr{padding:9px 0;border-bottom:1px solid rgba(255,255,255,.025)}
.sr-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.sr-name{font-size:11px;color:var(--text)}
.sr-right{display:flex;align-items:center;gap:7px}
.sr-score{font-size:11px;font-weight:700;color:var(--cyan);font-family:var(--dsp)}
.sr-wr{font-size:9px;color:var(--dim)}
.sr-bar{height:3px;background:rgba(255,255,255,.04);border-radius:2px;overflow:hidden}
.sr-fill{height:100%;transition:width .8s;border-radius:2px}
.sr-tr{margin-top:3px;font-size:9px;color:var(--dimmer)}
.best-tag{font-size:8px;padding:1px 5px;border-radius:2px;font-weight:700;letter-spacing:1px;
  background:rgba(0,255,148,.1);border:1px solid rgba(0,255,148,.2);color:var(--green)}
/* POSITIONS */
.pos-panel{grid-area:pos}
.pc{background:var(--s2);border-radius:3px;border-left:3px solid;padding:10px;
  margin-bottom:7px;animation:fu .3s ease;border:1px solid var(--b)}
@keyframes fu{from{opacity:0;transform:translateY(5px)}}
.pc-long{border-left-color:var(--green)!important}.pc-short{border-left-color:var(--red)!important}
.pc-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:7px}
.pc-sym{font-family:var(--dsp);font-size:15px;font-weight:700;letter-spacing:2px}
.pc-tags{display:flex;gap:3px;margin-top:4px;flex-wrap:wrap;align-items:center}
.pc-type{font-size:8px;font-weight:700;padding:2px 6px;border-radius:2px;letter-spacing:1px;border:1px solid}
.lt{background:rgba(0,255,148,.1);border-color:rgba(0,255,148,.2);color:var(--green)}
.st{background:rgba(255,45,85,.1);border-color:rgba(255,45,85,.2);color:var(--red)}
.lev-t{font-size:8px;color:var(--dim);border:1px solid var(--b);padding:2px 5px;border-radius:2px}
.conf-t{font-size:8px;padding:2px 5px;border-radius:2px;background:rgba(191,95,255,.08);border:1px solid rgba(191,95,255,.2);color:var(--purple)}
.pc-pnl-wrap{text-align:right}
.pc-pnl-main{font-family:var(--dsp);font-size:17px;font-weight:700;letter-spacing:1px}
.pc-pnl-pct{font-size:9px;color:var(--dim)}
.pc-extr{font-size:8px;color:var(--dimmer);margin-top:1px}
.pc-prices{display:grid;grid-template-columns:1fr 1fr;gap:2px 12px;font-size:9px;color:var(--dim);margin-bottom:7px}
.pc-prices span{display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.025)}
.pc-prices b{color:var(--text)}
.prog-wrap{margin:6px 0 7px}
.prog-lbl{display:flex;justify-content:space-between;font-size:8px;margin-bottom:2px}
.prog-bg{height:5px;background:rgba(255,255,255,.04);border-radius:2px;overflow:hidden;position:relative}
.prog-fill{height:100%;border-radius:2px;transition:width .6s ease}
.prog-mk{position:absolute;top:-2px;width:2px;height:9px;background:rgba(255,255,255,.5);border-radius:1px;transition:left .6s ease}
.pc-inds{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}
.ind-c{font-size:8px;padding:2px 6px;border-radius:2px;border:1px solid var(--b);color:var(--dim);letter-spacing:.3px}
.ic-l{border-color:rgba(0,229,255,.3);color:var(--cyan)}
.ic-w{border-color:rgba(255,214,10,.3);color:var(--yellow)}
.ic-d{border-color:rgba(255,45,85,.3);color:var(--red)}
.pc-ai{background:rgba(191,95,255,.04);border:1px solid rgba(191,95,255,.15);border-radius:2px;padding:6px 9px}
.pc-ai-l{font-size:8px;letter-spacing:2px;color:var(--purple);margin-bottom:2px;font-weight:700}
.pc-ai-t{font-size:9px;color:rgba(191,95,255,.75);line-height:1.7}
.chart-btn{font-size:8px;padding:2px 7px;border:1px solid var(--b3);border-radius:2px;
  background:none;color:var(--cyan);cursor:pointer;letter-spacing:1px;font-family:var(--mono);transition:.15s}
.chart-btn:hover{border-color:var(--cyan);background:rgba(0,229,255,.05)}
/* HISTORY */
.hist-panel{grid-area:hist}
.hf{padding:5px 10px;border-bottom:1px solid var(--b);display:flex;gap:5px;align-items:center}
.hf-btn{padding:2px 7px;background:none;border:1px solid var(--b);border-radius:2px;color:var(--dim);
  font-family:var(--mono);font-size:9px;cursor:pointer;transition:.15s;letter-spacing:.5px}
.hf-btn.active,.hf-btn:hover{border-color:var(--cyan);color:var(--cyan)}
.hi{display:flex;align-items:center;gap:9px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.025);animation:fu .3s ease}
.hi-b{width:34px;height:34px;border-radius:2px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;letter-spacing:.5px;flex-shrink:0}
.wb{background:rgba(0,255,148,.1);color:var(--green);border:1px solid rgba(0,255,148,.2)}
.lb{background:rgba(255,45,85,.1);color:var(--red);border:1px solid rgba(255,45,85,.2)}
.hi-info{flex:1;min-width:0}
.hi-sym{font-weight:700;font-size:11px;letter-spacing:.3px}
.hi-meta{font-size:9px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hi-pnl{text-align:right;font-size:11px;font-weight:700;flex-shrink:0}
.hi-pct{font-size:9px;color:var(--dimmer);display:block;text-align:right}
/* LOG */
.log-panel{grid-area:log}
.li{padding:4px 0;border-bottom:1px solid rgba(255,255,255,.02);font-size:9px;line-height:1.6;animation:fu .3s ease}
.lt2{color:var(--dimmer);margin-right:7px}
.lv-info{color:var(--text)}.lv-success{color:var(--green)}.lv-trade{color:var(--cyan)}
.lv-warn{color:var(--yellow)}.lv-error{color:var(--red)}
/* MODAL */
.moverlay{position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:500;display:none;align-items:center;justify-content:center;backdrop-filter:blur(6px)}
.moverlay.open{display:flex}
.modal{background:var(--s1);border:1px solid var(--b3);border-radius:4px;width:700px;max-width:96vw;max-height:88vh;overflow-y:auto}
.modal-hd{padding:12px 16px;border-bottom:1px solid var(--b);display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:var(--s1);z-index:5}
.modal-sym{font-family:var(--dsp);font-size:20px;font-weight:900;letter-spacing:3px}
.modal-close{background:none;border:1px solid var(--b2);color:var(--dim);width:26px;height:26px;border-radius:2px;cursor:pointer;font-size:12px}
.modal-close:hover{border-color:var(--red);color:var(--red)}
.modal-body{padding:12px 16px}
.ms-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:12px}
.ms{background:var(--s2);border:1px solid var(--b);border-radius:2px;padding:9px 11px}
.ms-l{font-size:8px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px}
.ms-v{font-size:13px;font-weight:700;font-family:var(--dsp)}
#modal-cv{width:100%;display:block;border-radius:2px}
.risk-panel{grid-area:risk}
.risk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;padding:12px}
.rg{background:var(--s2);border:1px solid var(--b);border-radius:3px;padding:12px}
.rg-lbl{font-size:9px;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center}
.rg-lbl span{color:var(--cyan);font-size:10px;font-weight:700;font-family:var(--dsp)}
.rg-input{width:100%;background:var(--s1);border:1px solid var(--b2);border-radius:2px;padding:7px 10px;
  color:var(--text);font-family:var(--mono);font-size:12px;font-weight:700;outline:none;transition:.15s}
.rg-input:focus{border-color:var(--cyan);box-shadow:0 0 8px rgba(0,229,255,0.15)}
.rg-input[type=range]{padding:4px 0;accent-color:var(--cyan);cursor:pointer;height:auto}
.rg-desc{font-size:8px;color:var(--dimmer);margin-top:4px;letter-spacing:.3px}
.risk-save{padding:9px 24px;background:linear-gradient(135deg,var(--cyan),var(--teal));
  border:none;border-radius:3px;color:var(--bg);font-family:var(--mono);font-size:11px;
  font-weight:700;letter-spacing:2px;cursor:pointer;transition:.2s;text-transform:uppercase}
.risk-save:hover{filter:brightness(1.15);box-shadow:0 0 20px rgba(0,229,255,0.3)}
.risk-save:active{transform:scale(.97)}
.risk-status{font-size:10px;margin-left:12px;opacity:0;transition:opacity .3s}
.lev-btns{display:flex;gap:4px}
.lev-btn{flex:1;padding:6px;background:none;border:1px solid var(--b2);border-radius:2px;
  color:var(--dim);font-family:var(--mono);font-size:10px;cursor:pointer;transition:.15s;text-align:center}
.lev-btn.active{border-color:var(--cyan);color:var(--cyan);background:rgba(0,229,255,.08)}
</style>
</head>
<body>

<div class="ticker-wrap"><div class="ticker-track" id="ticker"></div></div>

<header>
  <div>
    <div class="logo">AI TRADING BOT</div>
    <div class="logo-sub">BINANCE FUTURES · REAL DATA · SIMULATED</div>
  </div>
  <div class="hdr-stats">
    <div class="hs"><div class="hs-l">Bakiye</div><div class="hs-v c-cyan" id="h-bal">$10,000</div></div>
    <div class="sep"></div>
    <div class="hs"><div class="hs-l">PnL</div><div class="hs-v" id="h-pnl">$0</div></div>
    <div class="sep"></div>
    <div class="hs"><div class="hs-l">Win Rate</div><div class="hs-v" id="h-wr">50%</div></div>
    <div class="sep"></div>
    <div class="hs"><div class="hs-l">Drawdown</div><div class="hs-v c-yellow" id="h-dd">0%</div></div>
    <div class="sep"></div>
    <div class="hs"><div class="hs-l">P.Factor</div><div class="hs-v c-teal" id="h-pf">1.0</div></div>
  </div>
  <div class="hdr-ctrl">
    <div class="upt" id="upt">00:00:00</div>
    <div class="sdot" id="sdot"></div>
    <div class="stxt c-dim" id="stxt">DURDURULDU</div>
    <button class="btn btn-go" id="btn-start" onclick="startBot()">▶ BASLAT</button>
    <button class="btn btn-stop" id="btn-stop" onclick="stopBot()" disabled>■ DURDUR</button>
  </div>
</header>

<div class="main">
  <div class="stats-row">
    <div class="sc"><div class="sc-lbl">Portfoy</div><div class="sc-val c-cyan" id="s-bal">$10,000</div><div class="sc-sub">Baslangic: $10,000</div></div>
    <div class="sc"><div class="sc-lbl">Toplam PnL</div><div class="sc-val" id="s-pnl">$0</div><div class="sc-sub" id="s-pnl-pct">0.00%</div></div>
    <div class="sc"><div class="sc-lbl">Win Rate</div><div class="sc-val" id="s-wr">50%</div><div class="sc-sub" id="s-wl">W:0 / L:0</div></div>
    <div class="sc"><div class="sc-lbl">Profit Factor</div><div class="sc-val c-teal" id="s-pf">1.0</div><div class="sc-sub">Kazanc / Kayip</div></div>
    <div class="sc"><div class="sc-lbl">Drawdown</div><div class="sc-val c-yellow" id="s-dd">0%</div><div class="sc-sub">Zirve dusus</div></div>
    <div class="sc"><div class="sc-lbl">Acik Poz.</div><div class="sc-val c-purple" id="s-act">0/7</div><div class="sc-sub">Maks 7 pozisyon</div></div>
    <div class="sc"><div class="sc-lbl">Islem Sayisi</div><div class="sc-val c-orange" id="s-tr">0</div><div class="sc-sub" id="s-tr-sub">Toplam trade</div></div>
    <div class="sc"><div class="sc-lbl">Coin Sayisi</div><div class="sc-val c-cyan" id="s-coins">0</div><div class="sc-sub">Futures ciftleri</div></div>
  </div>

  <div class="coins-panel panel">
    <div class="ctoolbar">
      <span style="font-family:var(--dsp);font-size:10px;letter-spacing:2px">PIYASA</span>
      <input class="cinput" id="csrch" placeholder="Coin ara..." oninput="renderCoins()">
      <button class="sb active" onclick="setSortMode('change',this)">% DEGISIM</button>
      <button class="sb" onclick="setSortMode('volume',this)">HACIM</button>
      <button class="sb" onclick="setSortMode('name',this)">ISIM</button>
      <span style="margin-left:auto;font-size:9px;color:var(--dim)" id="coin-lbl">0 coin</span>
    </div>
    <div class="cg" id="cg"></div>
  </div>

  <div class="chart-panel panel">
    <div class="ph">
      <div class="ph-l">
        <div class="ph-title" id="ch-title">PNL GRAFIGI</div>
        <div class="badge bd-c" id="ch-badge">PORTFOY</div>
      </div>
      <div style="display:flex;gap:5px;align-items:center">
        <button class="mode-btn active" id="mb-pnl" onclick="showPnlChart()">PNL</button>
        <button class="mode-btn" id="mb-pr" onclick="setPriceMode()">FIYAT</button>
      </div>
    </div>
    <div class="ch-tb" id="ch-tb" style="display:none">
      <span style="font-size:9px;color:var(--dim);letter-spacing:1px">PERIYOT:</span>
      <button class="tf-btn active" onclick="setTf('1m',this)">1m</button>
      <button class="tf-btn" onclick="setTf('3m',this)">3m</button>
      <button class="tf-btn" onclick="setTf('5m',this)">5m</button>
      <button class="tf-btn" onclick="setTf('15m',this)">15m</button>
      <button class="tf-btn" onclick="setTf('1h',this)">1h</button>
      <button class="tf-btn" onclick="setTf('4h',this)">4h</button>
      <span id="ch-ohlc" style="margin-left:auto;font-size:9px;color:var(--dim)"></span>
    </div>
    <div id="cv-wrap"><canvas id="cv" height="210"></canvas><div id="cvtt"></div></div>
    <div class="ch-info" id="ch-info"></div>
  </div>

  <div class="strat-panel panel">
    <div class="ph">
      <div class="ph-l"><div class="ph-title">STRATEJI OGRENIMI</div><div class="badge bd-c">CANLI</div></div>
      <div class="badge bd-g" id="best-sb">EN IYI: --</div>
    </div>
    <div class="scroll" id="strats"></div>
  </div>

  <div class="pos-panel panel">
    <div class="ph">
      <div class="ph-l"><div class="ph-title">ACIK POZISYONLAR</div><div class="badge bd-c" id="pos-badge">0 AKTIF</div></div>
    </div>
    <div class="scroll" id="positions"><div class="empty">Pozisyon bekleniyor...</div></div>
  </div>

  <div class="hist-panel panel">
    <div class="ph">
      <div class="ph-l"><div class="ph-title">TRADE GECMISI</div><div class="badge bd-c" id="hist-badge">0 TRADE</div></div>
    </div>
    <div class="hf">
      <button class="hf-btn active" onclick="setHF('all',this)">TUMÜ</button>
      <button class="hf-btn" onclick="setHF('win',this)">KAZANCLAR</button>
      <button class="hf-btn" onclick="setHF('loss',this)">KAYIPLAR</button>
      <span style="margin-left:auto;font-size:9px;color:var(--dim)" id="hist-stats"></span>
    </div>
    <div class="scroll" id="history"><div class="empty">Trade bekleniyor...</div></div>
  </div>

  <div class="log-panel panel">
    <div class="ph">
      <div class="ph-l"><div class="ph-title">SISTEM LOGU</div><div class="badge bd-g">CANLI</div></div>
      <button class="hf-btn" onclick="document.getElementById('log').innerHTML='<div class=empty>Log temizlendi</div>'">TEMIZLE</button>
    </div>
    <div class="scroll" id="log"><div class="empty">Log bekleniyor...</div></div>
  </div>

  <!-- RISK PANELİ -->
  <div class="risk-panel panel">
    <div class="ph">
      <div class="ph-l">
        <div class="ph-title">⚙ RISK & BOT AYARLARI</div>
        <div class="badge bd-y">CANLI DEGİSTİR</div>
      </div>
      <div style="display:flex;align-items:center">
        <button class="risk-save" onclick="saveRisk()">💾 KAYDET</button>
        <span class="risk-status c-green" id="risk-status">✓ Kaydedildi</span>
      </div>
    </div>
    <div class="risk-grid">
      <div class="rg">
        <div class="rg-lbl">Max Pozisyon <span id="rv-maxpos">7</span></div>
        <input class="rg-input" type="range" id="r-maxpos" min="1" max="20" value="7" oninput="document.getElementById('rv-maxpos').textContent=this.value">
        <div class="rg-desc">Aynı anda açılabilecek maksimum pozisyon sayısı</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Pozisyon Büyüklüğü % <span id="rv-size">9</span>%</div>
        <input class="rg-input" type="range" id="r-size" min="1" max="50" value="9" oninput="document.getElementById('rv-size').textContent=this.value">
        <div class="rg-desc">Her trade için bakiyenin yüzdesi</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Take Profit % <span id="rv-tp">2.0</span>%</div>
        <input class="rg-input" type="number" id="r-tp" value="2.0" min="0.1" max="50" step="0.1" style="font-size:18px;text-align:center">
        <div class="rg-desc">Kâr hedefi (kaldıraçla çarpılır)</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Stop Loss % <span id="rv-sl">0.8</span>%</div>
        <input class="rg-input" type="number" id="r-sl" value="0.8" min="0.1" max="20" step="0.1" style="font-size:18px;text-align:center">
        <div class="rg-desc">Zarar kes (kaldıraçla çarpılır)</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Kaldıraç</div>
        <div class="lev-btns" id="lev-btns">
          <div class="lev-btn active" onclick="setLev(0,this)">RAST.</div>
          <div class="lev-btn" onclick="setLev(2,this)">2x</div>
          <div class="lev-btn" onclick="setLev(3,this)">3x</div>
          <div class="lev-btn" onclick="setLev(5,this)">5x</div>
          <div class="lev-btn" onclick="setLev(10,this)">10x</div>
          <div class="lev-btn" onclick="setLev(20,this)">20x</div>
        </div>
        <div class="rg-desc">0 = rastgele (2x/3x/5x/10x)</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Min Sinyal Skoru <span id="rv-score">3</span></div>
        <input class="rg-input" type="range" id="r-score" min="1" max="10" value="3" oninput="document.getElementById('rv-score').textContent=this.value">
        <div class="rg-desc">Düşük = daha fazla trade, yüksek = daha seçici</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Min Güven % <span id="rv-conf">42</span>%</div>
        <input class="rg-input" type="range" id="r-conf" min="10" max="95" value="42" oninput="document.getElementById('rv-conf').textContent=this.value">
        <div class="rg-desc">AI güven eşiği</div>
      </div>
      <div class="rg">
        <div class="rg-lbl">Tarama Büyüklüğü <span id="rv-scan">12</span></div>
        <input class="rg-input" type="range" id="r-scan" min="3" max="50" value="12" oninput="document.getElementById('rv-scan').textContent=this.value">
        <div class="rg-desc">Her turda kaç coin taransın (yüksek = daha hızlı)</div>
      </div>
    </div>
  </div>
</div>

<div class="moverlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-hd">
      <div>
        <div class="modal-sym" id="m-sym">--</div>
        <div style="font-size:9px;color:var(--dim);margin-top:1px;letter-spacing:1px" id="m-sub">--</div>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="ms-grid">
        <div class="ms"><div class="ms-l">Fiyat</div><div class="ms-v c-cyan" id="m-price">--</div></div>
        <div class="ms"><div class="ms-l">24s Degisim</div><div class="ms-v" id="m-chg">--</div></div>
        <div class="ms"><div class="ms-l">24s Yüksek</div><div class="ms-v c-green" id="m-hi">--</div></div>
        <div class="ms"><div class="ms-l">24s Düsük</div><div class="ms-v c-red" id="m-lo">--</div></div>
      </div>
      <canvas id="modal-cv" height="180"></canvas>
      <div style="padding:7px 0;font-size:9px;color:var(--dim);text-align:center" id="m-vol">--</div>
    </div>
  </div>
</div>

<script>
let D={},running=false,chartMode='pnl',curSym=null,curTf='5m',sortMode='change',hFilter='all';
let tickerInit=false,cvHover=false,cvMX=0;

const fp=n=>{
  if(n==null)return'--';if(n===0)return'$0';
  const a=Math.abs(n);const d=a<0.0001?8:a<0.01?6:a<1?4:2;
  return n.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
};
const fpp=n=>(n>=0?'+$':'−$')+Math.abs(n).toFixed(2);
const fpct=n=>(n>=0?'+':'')+n.toFixed(2)+'%';
const cl=n=>n>=0?'c-green':'c-red';

function startBot(){fetch('/api/start').then(()=>{running=true;syncUI()})}
function stopBot(){fetch('/api/stop').then(()=>{running=false;syncUI()})}
function syncUI(){
  const on=D.running||running;
  document.getElementById('sdot').className='sdot'+(on?' on':'');
  document.getElementById('stxt').textContent=on?'CALISIYOR':'DURDURULDU';
  document.getElementById('stxt').className='stxt '+(on?'c-green':'c-dim');
  document.getElementById('btn-start').disabled=on;
  document.getElementById('btn-stop').disabled=!on;
}

function buildTicker(){
  const coins=D.coins||{};const keys=Object.keys(coins).slice(0,40);
  if(!keys.length||tickerInit)return;tickerInit=true;
  let h='';
  for(let pass=0;pass<2;pass++)keys.forEach(s=>{
    const c=coins[s];const chg=c.change||0;
    h+=`<div class="tick-item"><span class="t-sym">${s.replace('USDT','')}</span><span class="t-price">$${fp(c.price)}</span><span class="${chg>=0?'t-up':'t-dn'}">${chg>=0?'+':''}${chg.toFixed(2)}%</span></div>`;
  });
  document.getElementById('ticker').innerHTML=h;
}
function updateTicker(){
  const coins=D.coins||{};
  document.querySelectorAll('.tick-item').forEach(el=>{
    const sym=el.querySelector('.t-sym')?.textContent+'USDT';const c=coins[sym];if(!c)return;
    const p=el.querySelector('.t-price');const ch=el.querySelector('[class^="t-"]~span,[class*=" t-"]');
    if(p)p.textContent='$'+fp(c.price);
    const chEl=el.querySelector('.t-up,.t-dn');
    if(chEl){const chg=c.change||0;chEl.textContent=(chg>=0?'+':'')+chg.toFixed(2)+'%';chEl.className=chg>=0?'t-up':'t-dn';}
  });
}

let coinSort='change';
function setSortMode(m,btn){coinSort=m;document.querySelectorAll('.sb').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderCoins()}
function renderCoins(){
  const coins=D.coins||{};const pos=new Set(Object.keys(D.positions||{}));
  const q=document.getElementById('csrch').value.toUpperCase();
  let entries=Object.entries(coins).filter(([s])=>s.replace('USDT','').includes(q));
  if(coinSort==='change')entries.sort((a,b)=>Math.abs(b[1].change)-Math.abs(a[1].change));
  else if(coinSort==='volume')entries.sort((a,b)=>b[1].quoteVolume-a[1].quoteVolume);
  else entries.sort((a,b)=>a[0].localeCompare(b[0]));
  let h='';
  entries.forEach(([s,c])=>{
    const label=s.replace('USDT','');const hp=pos.has(s);const chg=c.change||0;
    h+=`<div class="cc${hp?' has-pos':''}" onclick="openModal('${s}')"><div class="cc-n">${label}</div><div class="cc-p">$${fp(c.price)}</div><div class="cc-c ${chg>=0?'up-ch':'dn-ch'}">${chg>=0?'+':''}${chg.toFixed(2)}%</div></div>`;
  });
  document.getElementById('cg').innerHTML=h||'<div style="padding:16px;color:var(--dim);font-size:10px">Yukleniyor...</div>';
  document.getElementById('coin-lbl').textContent=entries.length+' coin';
  document.getElementById('s-coins').textContent=D.coin_count||0;
}

function buildStats(){
  const pnl=D.total_pnl||0,pct=D.total_pnl_pct||0,wr=D.wr||50,dd=D.drawdown||0,pf=D.profit_factor||1;
  const wins=D.wins||0,losses=(D.trades||0)-wins;
  document.getElementById('h-bal').textContent='$'+(D.balance||0).toLocaleString('en-US',{minimumFractionDigits:2});
  document.getElementById('h-pnl').textContent=fpp(pnl);document.getElementById('h-pnl').className='hs-v '+(pnl>=0?'c-green':'c-red');
  document.getElementById('h-wr').textContent=wr.toFixed(1)+'%';document.getElementById('h-wr').className='hs-v '+(wr>=50?'c-green':'c-red');
  document.getElementById('h-dd').textContent=dd.toFixed(2)+'%';
  document.getElementById('h-pf').textContent=pf.toFixed(2);
  document.getElementById('upt').textContent=D.uptime||'00:00:00';
  document.getElementById('s-bal').textContent='$'+(D.balance||0).toLocaleString('en-US',{minimumFractionDigits:2});
  document.getElementById('s-pnl').textContent=fpp(pnl);document.getElementById('s-pnl').className='sc-val '+(pnl>=0?'c-green':'c-red');
  document.getElementById('s-pnl-pct').textContent=(pct>=0?'+':'')+pct+'%';
  document.getElementById('s-wr').textContent=wr.toFixed(1)+'%';document.getElementById('s-wr').className='sc-val '+(wr>=50?'c-green':'c-red');
  document.getElementById('s-wl').textContent=`W:${wins} / L:${losses}`;
  document.getElementById('s-pf').textContent=pf.toFixed(2);document.getElementById('s-dd').textContent=dd.toFixed(2)+'%';
  document.getElementById('s-act').textContent=(D.active||0)+'/7';document.getElementById('s-tr').textContent=D.trades||0;
}

function initHover(){
  const cv=document.getElementById('cv');
  cv.addEventListener('mousemove',e=>{cvHover=true;cvMX=e.offsetX;if(chartMode==='pnl')drawPnlChart(D.curve||[])});
  cv.addEventListener('mouseleave',()=>{cvHover=false;document.getElementById('cvtt').style.display='none';if(chartMode==='pnl')drawPnlChart(D.curve||[])});
}

function drawPnlChart(curve){
  const cv=document.getElementById('cv');const ctx=cv.getContext('2d');
  const DPR=window.devicePixelRatio||1;const W=cv.parentElement.offsetWidth;const H=210;
  cv.width=W*DPR;cv.height=H*DPR;cv.style.width=W+'px';cv.style.height=H+'px';ctx.scale(DPR,DPR);ctx.clearRect(0,0,W,H);
  const pad={t:14,r:14,b:22,l:68};const cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;
  if(curve.length<2){ctx.fillStyle='rgba(74,110,140,0.35)';ctx.font='11px JetBrains Mono';ctx.textAlign='center';ctx.fillText('Bot baslatildiktan sonra grafik olusacak',W/2,H/2);return;}
  const mn=Math.min(...curve)*0.9995,mx=Math.max(...curve)*1.0005,rng=mx-mn||100;
  const toX=i=>pad.l+(i/(curve.length-1))*cw;const toY=v=>pad.t+ch-((v-mn)/rng)*ch;
  for(let i=0;i<=5;i++){
    const y=pad.t+(ch/5)*i;ctx.strokeStyle='rgba(21,32,48,0.9)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(pad.l+cw,y);ctx.stroke();
    const val=mx-(rng/5)*i;ctx.fillStyle='rgba(74,110,140,0.55)';ctx.font='9px JetBrains Mono';ctx.textAlign='right';ctx.fillText('$'+val.toFixed(0).replace(/\\B(?=(\\d{3})+(?!\\d))/g,','),pad.l-4,y+3);
  }
  if(10000>=mn&&10000<=mx){const by=toY(10000);ctx.strokeStyle='rgba(74,110,140,0.3)';ctx.lineWidth=1;ctx.setLineDash([3,5]);ctx.beginPath();ctx.moveTo(pad.l,by);ctx.lineTo(pad.l+cw,by);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='rgba(74,110,140,0.45)';ctx.font='8px JetBrains Mono';ctx.textAlign='left';ctx.fillText('$10,000',pad.l+4,by-3);}
  const pts=curve.map((v,i)=>({x:toX(i),y:toY(v),v}));
  const isUp=curve[curve.length-1]>=curve[0];const lnC=isUp?'#00ff94':'#ff2d55';
  const grad=ctx.createLinearGradient(0,pad.t,0,pad.t+ch);
  grad.addColorStop(0,isUp?'rgba(0,255,148,0.14)':'rgba(255,45,85,0.14)');grad.addColorStop(1,'rgba(0,0,0,0)');
  ctx.beginPath();ctx.moveTo(pts[0].x,pad.t+ch);pts.forEach(p=>ctx.lineTo(p.x,p.y));ctx.lineTo(pts[pts.length-1].x,pad.t+ch);ctx.closePath();ctx.fillStyle=grad;ctx.fill();
  ctx.beginPath();pts.forEach((p,i)=>i===0?ctx.moveTo(p.x,p.y):ctx.lineTo(p.x,p.y));ctx.strokeStyle=lnC;ctx.lineWidth=1.8;ctx.shadowColor=lnC;ctx.shadowBlur=7;ctx.stroke();ctx.shadowBlur=0;
  const lp=pts[pts.length-1];ctx.beginPath();ctx.arc(lp.x,lp.y,4,0,Math.PI*2);ctx.fillStyle=lnC;ctx.fill();ctx.strokeStyle='rgba(3,6,14,.8)';ctx.lineWidth=2;ctx.stroke();
  if(cvHover&&cvMX>=pad.l&&cvMX<=pad.l+cw){
    const nX=(cvMX-pad.l)/cw;const idx=Math.min(Math.round(nX*(curve.length-1)),curve.length-1);
    if(idx>=0&&idx<pts.length){
      const hp=pts[idx];
      ctx.strokeStyle='rgba(255,255,255,.12)';ctx.lineWidth=1;ctx.setLineDash([3,3]);
      ctx.beginPath();ctx.moveTo(hp.x,pad.t);ctx.lineTo(hp.x,pad.t+ch);ctx.stroke();
      ctx.beginPath();ctx.moveTo(pad.l,hp.y);ctx.lineTo(pad.l+cw,hp.y);ctx.stroke();ctx.setLineDash([]);
      ctx.beginPath();ctx.arc(hp.x,hp.y,5,0,Math.PI*2);ctx.fillStyle=lnC;ctx.fill();
      const tt=document.getElementById('cvtt');const pv=hp.v-10000;const times=D.pnl_times||[];
      tt.innerHTML=`<div style="color:var(--cyan);font-size:9px;margin-bottom:2px">${times[idx]||'--'}</div><div>Bakiye: <b style="color:var(--cyan)">$${hp.v.toLocaleString('en-US',{minimumFractionDigits:2})}</b></div><div>PnL: <b style="color:${pv>=0?'var(--green)':'var(--red)'}">${fpp(pv)}</b></div><div style="color:var(--dimmer)">Trade #${idx+1}</div>`;
      tt.style.display='block';let tx=hp.x+12;if(tx+145>W)tx=hp.x-150;tt.style.left=tx+'px';tt.style.top=(hp.y-18)+'px';
    }
  }
}

function drawCandles(klines,entry,tp,sl,posType,canvasId,H){
  const cv=document.getElementById(canvasId);const ctx=cv.getContext('2d');
  const DPR=window.devicePixelRatio||1;const W=cv.parentElement.offsetWidth;
  cv.width=W*DPR;cv.height=H*DPR;cv.style.width=W+'px';cv.style.height=H+'px';ctx.scale(DPR,DPR);ctx.clearRect(0,0,W,H);
  if(!klines||klines.length<3){ctx.fillStyle='rgba(74,110,140,0.35)';ctx.font='10px JetBrains Mono';ctx.textAlign='center';ctx.fillText('Grafik verisi yukleniyor...',W/2,H/2);return;}
  const pad={t:12,r:12,b:20,l:64};const cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;
  let mn=Math.min(...klines.map(k=>k.l)),mx=Math.max(...klines.map(k=>k.h));
  if(tp){mn=Math.min(mn,sl||tp);mx=Math.max(mx,tp)}
  const ext=(mx-mn)*0.06;mn-=ext;mx+=ext;const rng=mx-mn||1;
  const toY=v=>pad.t+ch-((v-mn)/rng)*ch;
  for(let i=0;i<=4;i++){
    const y=pad.t+(ch/4)*i;ctx.strokeStyle='rgba(21,32,48,0.9)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(pad.l+cw,y);ctx.stroke();
    const val=mx-(rng/4)*i;ctx.fillStyle='rgba(74,110,140,0.55)';ctx.font='8px JetBrains Mono';ctx.textAlign='right';ctx.fillText('$'+fp(val),pad.l-3,y+3);
  }
  [{v:entry,color:'rgba(0,229,255,0.8)',lbl:'ENTRY',dash:[5,3]},{v:tp,color:'rgba(0,255,148,0.8)',lbl:'TP',dash:[6,3]},{v:sl,color:'rgba(255,45,85,0.8)',lbl:'SL',dash:[6,3]}].forEach(({v,color,lbl,dash})=>{
    if(!v||v<mn||v>mx)return;const y=toY(v);ctx.strokeStyle=color;ctx.lineWidth=1.2;ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(pad.l+cw,y);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=color;ctx.font='bold 8px JetBrains Mono';ctx.textAlign='left';ctx.fillText(lbl,pad.l+3,y-2);ctx.textAlign='right';ctx.fillText('$'+fp(v),pad.l+cw-2,y-2);
  });
  const n=klines.length;const gap=Math.floor(cw/n);const bw=Math.max(2,gap-2);
  klines.forEach((k,i)=>{
    const x=pad.l+i*gap+gap/2;const isUp=k.c>=k.o;const color=isUp?'#00ff94':'#ff2d55';
    ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,toY(k.h));ctx.lineTo(x,toY(k.l));ctx.stroke();
    const by=toY(Math.max(k.o,k.c));const bh=Math.max(1,toY(Math.min(k.o,k.c))-by);
    ctx.fillStyle=isUp?'rgba(0,255,148,0.75)':'rgba(255,45,85,0.75)';ctx.fillRect(x-bw/2,by,bw,bh);
  });
  const lp=klines[klines.length-1].c;const lpy=toY(lp);
  ctx.strokeStyle='rgba(255,214,10,0.45)';ctx.lineWidth=1;ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(pad.l,lpy);ctx.lineTo(pad.l+cw,lpy);ctx.stroke();ctx.setLineDash([]);
}

function showPnlChart(){
  chartMode='pnl';curSym=null;
  document.getElementById('ch-title').textContent='PNL GRAFIGI';
  document.getElementById('ch-badge').textContent='PORTFOY';document.getElementById('ch-badge').className='badge bd-c';
  document.getElementById('ch-tb').style.display='none';document.getElementById('ch-info').textContent='';
  document.getElementById('mb-pnl').classList.add('active');document.getElementById('mb-pr').classList.remove('active');
  drawPnlChart(D.curve||[]);
}
function setPriceMode(){document.getElementById('mb-pr').classList.add('active');document.getElementById('mb-pnl').classList.remove('active')}
function showCandleChart(sym){
  chartMode='candle';curSym=sym;curTf='5m'; // Reset to 5m
  document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active'));
  document.querySelector('.tf-btn[onclick*="1m"]')?.classList.add('active');
  
  const pos=(D.positions||{})[sym];const c=(D.coins||{})[sym]||{};
  document.getElementById('ch-title').textContent=sym.replace('USDT','')+'/USDT';
  document.getElementById('ch-badge').textContent=pos?pos.type+' '+pos.lev+'x':'CHART';
  document.getElementById('ch-badge').className='badge '+(pos?pos.type==='LONG'?'bd-g':'bd-r':'bd-c');
  document.getElementById('ch-tb').style.display='flex';setPriceMode();
  const kl=pos?pos.klines:[];
  drawCandles(kl,pos?.entry,pos?.tp,pos?.sl,pos?.type,'cv',210);
  const vol=((c.quoteVolume||0)/1e6).toFixed(1);
  document.getElementById('ch-info').innerHTML=`<span>Fiyat: <b style="color:var(--cyan)">$${fp(c.price)}</b></span><span>24s: <b class="${cl(c.change)}">${fpct(c.change||0)}</b></span><span>Vol: <b>${vol}M USDT</b></span>${pos?`<span>PnL: <b class="${cl(pos.pnl)}">${fpp(pos.pnl)}</b></span>`:''}`;
}
// Auto-refresh chart if modal is open
async function refreshOpenChart(){
  if(chartMode==='candle'&&curSym){
    const pos=(D.positions||{})[curSym];
    
    // If position exists, use its klines (always 5m for positions)
    if(pos&&pos.klines&&pos.klines.length>0&&curTf==='5m'){
      drawCandles(pos.klines,pos?.entry,pos?.tp,pos?.sl,pos?.type,'cv',210);
      return;
    }
    
    // Otherwise fetch klines for current timeframe
    try{
      const r=await fetch(`/api/klines?sym=${curSym}&tf=${curTf}&limit=80`);
      const data=await r.json();
      if(data.klines&&data.klines.length>0){
        drawCandles(data.klines,pos?.entry,pos?.tp,pos?.sl,pos?.type,'cv',210);
      }
    }catch(e){console.error('Chart refresh error:',e);}
  }
}
async function setTf(tf,btn){
  curTf=tf;
  document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  if(!curSym)return;
  
  // Fetch klines for new timeframe
  try{
    const r=await fetch(`/api/klines?sym=${curSym}&tf=${tf}&limit=80`);
    const data=await r.json();
    if(data.klines&&data.klines.length>0){
      const pos=(D.positions||{})[curSym];
      drawCandles(data.klines,pos?.entry,pos?.tp,pos?.sl,pos?.type,'cv',210);
    }
  }catch(e){console.error('Timeframe change error:',e);}
}

function buildPositions(){
  const pos=D.positions||{};const keys=Object.keys(pos);
  document.getElementById('pos-badge').textContent=keys.length+' AKTIF';document.getElementById('pos-badge').className='badge '+(keys.length?'bd-g':'bd-c');
  if(!keys.length){document.getElementById('positions').innerHTML='<div class="empty">Acik pozisyon yok</div>';return;}
  let h='';
  keys.forEach(sym=>{
    const p=pos[sym];const isL=p.type==='LONG';const ind=p.ind||{};const rsi=ind.rsi||0;
    const range=Math.abs(p.tp-p.sl)||1;let prog=50;
    if(isL)prog=Math.min(100,Math.max(0,(p.cur-p.sl)/range*100));else prog=Math.min(100,Math.max(0,(p.sl-p.cur)/range*100));
    const progC=p.pnl>=0?'var(--green)':'var(--red)';
    const secs=Math.round((Date.now()-new Date(p.t0).getTime())/1000);
    const dur=secs<60?secs+'s':secs<3600?Math.floor(secs/60)+'m':Math.floor(secs/3600)+'h';
    h+=`<div class="pc pc-${isL?'long':'short'}">
      <div class="pc-top">
        <div><div class="pc-sym">${sym.replace('USDT','')}<span style="font-size:11px;color:var(--dim)">/USDT</span></div>
          <div class="pc-tags">
            <span class="pc-type ${isL?'lt':'st'}">${p.type}</span>
            <span class="lev-t">${p.lev}x</span>
            <span class="conf-t">AI ${(p.conf||0).toFixed(0)}%</span>
            <span class="ind-c" style="background:rgba(0,229,255,0.15);color:var(--cyan);font-size:9px;padding:3px 6px">$${(p.sz||0).toFixed(0)}</span>
            <span style="font-size:8px;color:var(--dimmer);margin-left:2px">${dur}</span>
          </div></div>
        <div class="pc-pnl-wrap"><div class="pc-pnl-main ${cl(p.pnl)}">${fpp(p.pnl)}</div><div class="pc-pnl-pct">${fpct(p.pnl_pct||0)}</div><div class="pc-extr">Max:${fpp(p.max_pnl)} Min:${fpp(p.min_pnl)}</div></div>
      </div>
      <div class="pc-prices">
        <span>Pozisyon <b style="color:var(--cyan)">$${(p.sz||0).toFixed(2)}</b></span>
        <span>Giris <b>$${fp(p.entry)}</b></span>
        <span>Anlik <b>$${fp(p.cur)}</b></span>
        <span>TP <b style="color:var(--green)">$${fp(p.tp)}</b></span>
        <span>SL <b style="color:var(--red)">$${fp(p.sl)}</b></span>
      </div>
      <div class="prog-wrap">
        <div class="prog-lbl"><span style="color:var(--red)">SL</span><span style="color:var(--dim)">${prog.toFixed(0)}%</span><span style="color:var(--green)">TP</span></div>
        <div class="prog-bg"><div class="prog-fill" style="width:${prog}%;background:${progC}"></div><div class="prog-mk" style="left:${prog}%"></div></div>
      </div>
      <div class="pc-inds">
        <span class="ind-c ${rsi<32?'ic-w':rsi>68?'ic-d':'ic-l'}">RSI ${rsi}</span>
        <span class="ind-c ic-l">Stoch ${ind.stoch||'--'}</span>
        <span class="ind-c">Vol x${ind.vr||'--'}</span>
        <span class="ind-c">ATR ${((ind.atr_pct)||0).toFixed(2)}%</span>
        <span class="ind-c">${p.strat}</span>
        <button class="chart-btn" onclick="showCandleChart('${sym}')">GRAFIK</button>
      </div>
      <div class="pc-ai"><div class="pc-ai-l">AI ANALIZ · SKOR ${p.score>=0?'+':''}${p.score}</div><div class="pc-ai-t">${(p.reasons||[]).join(' · ')||'Analiz yukleniyor...'}</div></div>
    </div>`;
  });
  document.getElementById('positions').innerHTML=h;
}

let hF='all';
function setHF(f,btn){hF=f;document.querySelectorAll('.hf-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');buildHistory()}
function buildHistory(){
  let hist=(D.history||[]);
  if(hF==='win')hist=hist.filter(t=>t.won);else if(hF==='loss')hist=hist.filter(t=>!t.won);
  const total=D.trades||0,wins=D.wins||0,losses=total-wins;
  document.getElementById('hist-badge').textContent=total+' TRADE';document.getElementById('hist-stats').textContent=`W:${wins} | L:${losses} | ${hist.length} gosterilen`;
  if(!hist.length){document.getElementById('history').innerHTML='<div class="empty">Trade bekleniyor...</div>';return;}
  let h='';
  hist.forEach(t=>{h+=`<div class="hi"><div class="hi-b ${t.won?'wb':'lb'}">${t.won?'WIN':'LOSS'}</div><div class="hi-info"><div class="hi-sym">${t.sym.replace('USDT','')} ${t.type} ${t.lev}x · <span style="color:var(--cyan)">$${(t.sz||0).toFixed(0)}</span></div><div class="hi-meta">${t.why} · ${t.ht} · ${t.strat} · ${t.time}</div></div><div><div class="hi-pnl ${t.won?'c-green':'c-red'}">${fpp(t.pnl)}</div><span class="hi-pct">${fpct(t.pnl_pct||0)}</span></div></div>`;});
  document.getElementById('history').innerHTML=h;
}

function buildStrategies(){
  const st=D.strategies||{};const sorted=Object.entries(st).sort((a,b)=>b[1].score-a[1].score);
  const maxS=sorted[0]?.[1]?.score||1;const best=sorted[0]?.[0]||'--';
  document.getElementById('best-sb').textContent='EN IYI: '+best;
  const grads=['linear-gradient(90deg,var(--cyan),var(--teal))','linear-gradient(90deg,var(--green),var(--teal))','linear-gradient(90deg,var(--purple),var(--cyan))','linear-gradient(90deg,var(--orange),var(--yellow))','linear-gradient(90deg,var(--teal),var(--green))'];
  let h='';
  sorted.forEach(([name,info],i)=>{
    const pct=Math.min((info.score/maxS)*100,100).toFixed(0);
    h+=`<div class="sr"><div class="sr-row"><span class="sr-name">${name}${i===0?' <span class="best-tag">EN IYI</span>':''}</span><div class="sr-right"><span class="sr-wr">${info.wr||0}% WR</span><span class="sr-score">${info.score.toFixed(2)}</span></div></div><div class="sr-bar"><div class="sr-fill" style="width:${pct}%;background:${grads[i%grads.length]}"></div></div><div class="sr-tr">${info.trades||0} trade</div></div>`;
  });
  document.getElementById('strats').innerHTML=h||'<div class="empty">--</div>';
}

function buildLog(){
  const evts=D.events||[];if(!evts.length){document.getElementById('log').innerHTML='<div class="empty">Log bekleniyor...</div>';return;}
  let h='';evts.forEach(e=>{h+=`<div class="li"><span class="lt2">[${e.t}]</span><span class="lv-${e.lvl}">${e.msg}</span></div>`;});
  document.getElementById('log').innerHTML=h;
}

function openModal(sym){
  const c=(D.coins||{})[sym]||{};const pos=(D.positions||{})[sym];
  document.getElementById('m-sym').textContent=sym.replace('USDT','')+'/USDT';
  document.getElementById('m-sub').textContent='Binance USDT-M Surekli Futures';
  document.getElementById('m-price').textContent='$'+fp(c.price);
  const chg=c.change||0;document.getElementById('m-chg').textContent=(chg>=0?'+':'')+chg.toFixed(2)+'%';document.getElementById('m-chg').className='ms-v '+(chg>=0?'c-green':'c-red');
  document.getElementById('m-hi').textContent='$'+fp(c.high);document.getElementById('m-lo').textContent='$'+fp(c.low);
  document.getElementById('m-vol').textContent=`24s Hacim: ${((c.quoteVolume||0)/1e6).toFixed(1)}M USDT | Islem: ${(c.count||0).toLocaleString()}`;
  document.getElementById('modal').classList.add('open');
  setTimeout(()=>{drawCandles(pos?.klines||[],pos?.entry,pos?.tp,pos?.sl,pos?.type,'modal-cv',180)},60);
}
function closeModal(){document.getElementById('modal').classList.remove('open')}

let selectedLev=0;
function setLev(v,btn){
  selectedLev=v;
  document.querySelectorAll('.lev-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
}
function loadRisk(r){
  if(!r)return;
  document.getElementById('r-maxpos').value=r.max_positions;document.getElementById('rv-maxpos').textContent=r.max_positions;
  document.getElementById('r-size').value=r.position_size_pct;document.getElementById('rv-size').textContent=r.position_size_pct;
  document.getElementById('r-tp').value=r.tp_pct;document.getElementById('rv-tp').textContent=r.tp_pct;
  document.getElementById('r-sl').value=r.sl_pct;document.getElementById('rv-sl').textContent=r.sl_pct;
  document.getElementById('r-score').value=r.min_score;document.getElementById('rv-score').textContent=r.min_score;
  document.getElementById('r-conf').value=r.min_conf;document.getElementById('rv-conf').textContent=r.min_conf;
  document.getElementById('r-scan').value=r.scan_size;document.getElementById('rv-scan').textContent=r.scan_size;
  selectedLev=r.leverage;
  document.querySelectorAll('.lev-btn').forEach(b=>b.classList.remove('active'));
  const levMap={0:0,2:1,3:2,5:3,10:4,20:5};
  const idx=levMap[r.leverage]??0;
  const btns=document.querySelectorAll('.lev-btn');
  if(btns[idx])btns[idx].classList.add('active');
}
async function saveRisk(){
  const payload={
    max_positions:parseInt(document.getElementById('r-maxpos').value),
    position_size_pct:parseInt(document.getElementById('r-size').value),
    tp_pct:parseFloat(document.getElementById('r-tp').value),
    sl_pct:parseFloat(document.getElementById('r-sl').value),
    min_score:parseInt(document.getElementById('r-score').value),
    min_conf:parseInt(document.getElementById('r-conf').value),
    scan_size:parseInt(document.getElementById('r-scan').value),
    leverage:selectedLev,
  };
  try{
    const r=await fetch('/api/risk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const d=await r.json();
    if(d.ok){
      const s=document.getElementById('risk-status');
      s.textContent='✓ Kaydedildi';s.className='risk-status c-green';s.style.opacity='1';
      setTimeout(()=>s.style.opacity='0',2500);
    }
  }catch(e){console.error(e);}
}

let firstPoll=true;
async function poll(){
  try{
    const r=await fetch('/api/status');if(!r.ok)return;
    D=await r.json();if(D.error)return;
    syncUI();buildStats();
    if(firstPoll){buildTicker();loadRisk(D.risk);firstPoll=false;}else updateTicker();
    renderCoins();buildPositions();buildHistory();buildStrategies();buildLog();
    if(chartMode==='pnl')drawPnlChart(D.curve||[]);
    else if(chartMode==='candle')refreshOpenChart();
  }catch(e){console.warn(e)}
}

initHover();poll();setInterval(poll,2000);
window.addEventListener('resize',()=>{if(chartMode==='pnl')drawPnlChart(D.curve||[]);else if(chartMode==='candle'&&curSym)showCandleChart(curSym)});
</script>
</body>
</html>"""


# ── HTTP HANDLER ───────────────────────────────────────────
engine_g=None

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            p=urlparse(self.path)
            if p.path=='/':
                self.send_response(200); self.send_header('Content-type','text/html;charset=utf-8'); self.end_headers()
                self.wfile.write(HTML.encode())
            elif p.path=='/api/status':
                self.send_response(200); self.send_header('Content-type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
                self.wfile.write(json.dumps(engine_g.state() if engine_g else {}).encode())
            elif p.path=='/api/start':
                self.send_response(200); self.send_header('Content-type','text/plain'); self.end_headers()
                if engine_g and not engine_g.running:
                    threading.Thread(target=engine_g.start,daemon=True).start()
                self.wfile.write(b'ok')
            elif p.path=='/api/stop':
                self.send_response(200); self.send_header('Content-type','text/plain'); self.end_headers()
                if engine_g: engine_g.stop()
                self.wfile.write(b'ok')
            elif p.path=='/api/klines':
                qs=parse_qs(p.query); sym=qs.get('sym',['BTCUSDT'])[0]; tf=qs.get('tf',['5m'])[0]; limit=int(qs.get('limit',['80'])[0])
                self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
                kl=engine_g.bc.klines(sym,tf,limit) if engine_g else []
                self.wfile.write(json.dumps({'klines':kl}).encode())
            elif p.path=='/api/debug':
                # FULL DEBUG ENDPOINT - Claude can monitor bot health
                self.send_response(200); self.send_header('Content-type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
                if not engine_g:
                    self.wfile.write(json.dumps({'error':'Engine not initialized'}).encode())
                    return
                
                debug_data={
                    'timestamp':datetime.now().isoformat(),
                    'uptime_seconds':int((datetime.now()-datetime.fromisoformat(engine_g.start_time)).total_seconds()) if engine_g.start_time else 0,
                    'running':engine_g.running,
                    'balance':engine_g.agent.balance,
                    'start_balance':engine_g.agent.start_balance,
                    'total_pnl':engine_g.agent.total_pnl(),
                    'total_pnl_pct':round(engine_g.agent.total_pnl()/engine_g.agent.start_balance*100,2),
                    'trades':engine_g.agent.trades,
                    'wins':engine_g.agent.wins,
                    'losses':engine_g.agent.trades-engine_g.agent.wins,
                    'win_rate':round(engine_g.agent.wr(),2),
                    'active_positions':len(engine_g.agent.positions),
                    'drawdown':engine_g.agent.drawdown(),
                    'profit_factor':engine_g.agent.profit_factor(),
                    'peak_balance':engine_g.agent.peak_balance,
                    'total_profit':engine_g.agent.total_profit,
                    'total_loss':engine_g.agent.total_loss,
                    'coin_count':len(engine_g.bc.symbols),
                    'risk_config':engine_g.agent.risk,
                    'positions_detail':{},
                    'recent_trades':engine_g.agent.history[:10],
                    'strategies':{},
                    'recent_logs':engine_g.events[:20],
                }
                
                # Position details with health indicators
                for sym,pos in engine_g.agent.positions.items():
                    tp_dist=abs(pos['tp']-pos['cur'])/pos['cur']*100
                    sl_dist=abs(pos['cur']-pos['sl'])/pos['cur']*100
                    duration_sec=int((datetime.now()-datetime.fromisoformat(pos['t0'])).total_seconds())
                    
                    debug_data['positions_detail'][sym]={
                        'type':pos['type'],'entry':pos['entry'],'current':pos['cur'],
                        'tp':pos['tp'],'sl':pos['sl'],'leverage':pos['lev'],
                        'size':pos['sz'],'pnl':round(pos['pnl'],2),'pnl_pct':round(pos['pnl_pct'],2),
                        'max_pnl':round(pos['max_pnl'],2),'min_pnl':round(pos['min_pnl'],2),
                        'tp_distance_pct':round(tp_dist,2),'sl_distance_pct':round(sl_dist,2),
                        'duration_seconds':duration_sec,'strategy':pos['strat']
                    }
                
                # Strategy performance
                for s,v in engine_g.agent.strategies.items():
                    st=engine_g.agent.strat_trades[s]
                    wr=st['wins']/st['total']*100 if st['total']>0 else 0
                    debug_data['strategies'][s]={'score':round(v,3),'trades':st['total'],'wins':st['wins'],'wr':round(wr,1)}
                
                self.wfile.write(json.dumps(debug_data).encode())
            
            # ── CANLI İZLEME API'LERİ ──────────────────────────────
            elif p.path=='/api/live-status':
                self.send_response(200); self.send_header('Content-type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
                if 'live_analyzer' in globals() and live_analyzer:
                    status = live_analyzer.get_current_status()
                    self.wfile.write(json.dumps(status).encode())
                else:
                    self.wfile.write(json.dumps({'error':'Live monitoring not active'}).encode())
            
            elif p.path=='/api/live-analysis':
                self.send_response(200); self.send_header('Content-type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
                if 'live_analyzer' in globals() and live_analyzer:
                    analysis = live_analyzer.analyze_for_claude()
                    self.wfile.write(json.dumps(analysis).encode())
                else:
                    self.wfile.write(json.dumps({'error':'Live monitoring not active'}).encode())
            
            elif p.path=='/api/live-report':
                self.send_response(200); self.send_header('Content-type','text/plain; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
                if 'live_analyzer' in globals() and live_analyzer:
                    report = live_analyzer.get_detailed_report()
                    self.wfile.write(report.encode('utf-8'))
                else:
                    self.wfile.write(b'Live monitoring not active')
            
            elif p.path=='/api/snapshot':
                self.send_response(200); self.send_header('Content-type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
                if 'live_analyzer' in globals() and live_analyzer:
                    snapshot = live_analyzer.take_snapshot()
                    self.wfile.write(json.dumps(snapshot).encode())
                else:
                    self.wfile.write(json.dumps({'error':'Live monitoring not active'}).encode())
            else:
                self.send_response(404); self.end_headers()
        except BrokenPipeError: pass
        except Exception as e: print(f"req: {e}")

    def do_POST(self):
        try:
            p=urlparse(self.path)
            length=int(self.headers.get('Content-Length',0))
            body=json.loads(self.rfile.read(length)) if length>0 else {}
            if p.path=='/api/risk':
                if engine_g:
                    for k,v in body.items():
                        if k in engine_g.agent.risk:
                            engine_g.agent.risk[k]=type(engine_g.agent.risk[k])(v)
                    engine_g.log(f"Risk ayarlari guncellendi: {body}","success")
                self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'ok':True,'risk':engine_g.agent.risk if engine_g else {}}).encode())
            else:
                self.send_response(404); self.end_headers()
        except BrokenPipeError: pass
        except Exception as e: print(f"post err: {e}"); self.send_response(500); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()

    def log_message(self,*a): pass

def main():
    global engine_g
    PORT = int(os.environ.get('PORT', 8080))
    print("\n"+"="*52+"\n  AI TRADING BOT v5.0\n  Real Binance Data - Simulated Trading\n"+"="*52+"\n")
    engine_g=Engine()
    
    # ── CANLI İZLEME SİSTEMİ ──────────────────────────────────
    try:
        from live_bot_monitor import LiveBotAnalyzer
        global live_analyzer
        live_analyzer = LiveBotAnalyzer(engine_g)
        live_analyzer.start_monitoring()
        print("🔴 Canlı izleme aktif - Claude sizi izliyor!")
        print("   API: /api/live-status, /api/live-analysis, /api/live-report")
    except ImportError:
        print("⚠️  Canlı izleme modülü bulunamadı (opsiyonel)")
        live_analyzer = None
    
    srv=HTTPServer(('0.0.0.0',PORT),H)
    print(f"-> Server running on port {PORT}")
    print("-> Ctrl+C ile durdur\n")
    try: srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDurduruluyor...")
        if live_analyzer: live_analyzer.stop_monitoring()
        if engine_g: engine_g.stop()
        srv.shutdown(); print("Tamam.")

if __name__=='__main__': main()
