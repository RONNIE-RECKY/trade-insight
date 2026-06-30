//+------------------------------------------------------------------+
//| PipHiveBridge.mq5                                                |
//|                                                                    |
//| Polls the PIP HIVE backend for queued signal orders and executes  |
//| them on THIS terminal — works against any broker's MT5 server,    |
//| demo or live, since it just acts on whatever account the terminal |
//| is already logged into. On a LIVE connection, the backend queues  |
//| orders as "awaiting confirmation" and won't return them from      |
//| /mt5/orders until the user confirms in the web app or via the     |
//| emailed link — this EA never sees a live order it wasn't told to  |
//| execute by a human (see apps/analysis-service/app/mt5_bridge.py). |
//|                                                                    |
//| Setup (required once per terminal):                               |
//|   Tools -> Options -> Expert Advisors -> check "Allow WebRequest  |
//|   for listed URL" and add your API base URL (e.g.                 |
//|   https://your-backend.up.railway.app). WebRequest calls to any   |
//|   URL not on that list are blocked by MT5 with error 4060.        |
//|                                                                    |
//| Not compiled or tested by an automated agent — no MT5 terminal is |
//| available in that environment. Compile in MetaEditor (F7) on a    |
//| demo account and watch the Experts/Journal tabs for errors before |
//| trusting it with even practice funds.                             |
//+------------------------------------------------------------------+
#property copyright "PIP HIVE"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input string InpApiBaseUrl   = "https://your-backend.up.railway.app"; // PIP HIVE API base URL (no trailing slash)
input string InpApiKey       = "";                                    // API key from the Auto-Trade page (MT5 demo connect)
input int    InpPollSeconds  = 5;                                     // how often to poll for new orders
input string InpSymbolSuffix = "";                                    // appended to symbols if your broker uses one (e.g. "m", ".a")
input int    InpMagicNumber  = 20260101;                              // magic number tagging trades opened by this EA
input int    InpSlippagePts  = 50;                                    // allowed slippage in points

CTrade trade;

//+------------------------------------------------------------------+
int OnInit()
{
   if(StringLen(InpApiKey) == 0)
   {
      Print("PipHiveBridge: InpApiKey is empty — connect MT5 on the Auto-Trade page first and paste the key here.");
      return INIT_PARAMETERS_INCORRECT;
   }
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippagePts);
   EventSetTimer(MathMax(InpPollSeconds, 2));
   Print("PipHiveBridge: started, polling ", InpApiBaseUrl, " every ", InpPollSeconds, "s");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   PollAndExecute();
}

//+------------------------------------------------------------------+
//| One poll cycle: fetch queued orders, execute each, report back   |
//+------------------------------------------------------------------+
void PollAndExecute()
{
   string url = InpApiBaseUrl + "/mt5/orders?api_key=" + InpApiKey;
   uchar  data[];
   uchar  result[];
   string resultHeaders;

   ResetLastError();
   int status = WebRequest("GET", url, "", 10000, data, result, resultHeaders);
   if(status == -1)
   {
      int err = GetLastError();
      if(err == 4060)
         Print("PipHiveBridge: WebRequest blocked. Add ", InpApiBaseUrl,
               " under Tools > Options > Expert Advisors > Allow WebRequest for listed URL.");
      else
         Print("PipHiveBridge: GET /mt5/orders failed, error ", err);
      return;
   }
   if(status != 200)
   {
      Print("PipHiveBridge: GET /mt5/orders returned HTTP ", status, ": ", CharArrayToString(result));
      return;
   }

   string body = CharArrayToString(result);
   ProcessOrdersJson(body);
}

//+------------------------------------------------------------------+
//| Minimal hand-rolled parsing for our fixed response shape:        |
//| {"orders":[{"id":1,"symbol":"EURUSD","action":"BUY","lot":0.1,   |
//|             "sl":1.23,"tp":1.25}, ...]}                          |
//+------------------------------------------------------------------+
void ProcessOrdersJson(string body)
{
   int arrStart = StringFind(body, "[");
   int arrEnd   = StringFind(body, "]");
   if(arrStart < 0 || arrEnd < 0 || arrEnd <= arrStart)
      return; // no orders array, or empty — nothing to do

   string arr = StringSubstr(body, arrStart + 1, arrEnd - arrStart - 1);
   if(StringLen(arr) == 0)
      return;

   int pos = 0;
   while(pos < StringLen(arr))
   {
      int objStart = StringFind(arr, "{", pos);
      if(objStart < 0) break;
      int objEnd = StringFind(arr, "}", objStart);
      if(objEnd < 0) break;

      string obj = StringSubstr(arr, objStart, objEnd - objStart + 1);
      ExecuteOrderFromJson(obj);

      pos = objEnd + 1;
   }
}

string JsonStringField(string obj, string key)
{
   string needle = "\"" + key + "\":\"";
   int i = StringFind(obj, needle);
   if(i < 0) return "";
   int start = i + StringLen(needle);
   int end = StringFind(obj, "\"", start);
   if(end < 0) return "";
   return StringSubstr(obj, start, end - start);
}

double JsonNumberField(string obj, string key)
{
   string needle = "\"" + key + "\":";
   int i = StringFind(obj, needle);
   if(i < 0) return 0.0;
   int start = i + StringLen(needle);
   int end = start;
   while(end < StringLen(obj))
   {
      ushort c = StringGetCharacter(obj, end);
      if((c >= '0' && c <= '9') || c == '.' || c == '-')
         end++;
      else
         break;
   }
   return StringToDouble(StringSubstr(obj, start, end - start));
}

long JsonIntField(string obj, string key)
{
   return (long)JsonNumberField(obj, key);
}

//+------------------------------------------------------------------+
void ExecuteOrderFromJson(string obj)
{
   long   id     = JsonIntField(obj, "id");
   string symbol = JsonStringField(obj, "symbol") + InpSymbolSuffix;
   string action = JsonStringField(obj, "action");
   double lot    = JsonNumberField(obj, "lot");
   double sl     = JsonNumberField(obj, "sl");
   double tp     = JsonNumberField(obj, "tp");

   if(!SymbolSelect(symbol, true))
   {
      Print("PipHiveBridge: order ", id, " — symbol ", symbol, " not found on this broker, skipping.");
      ReportResult(id, "failed", "", 0.0);
      return;
   }

   bool ok;
   if(action == "BUY")
      ok = trade.Buy(lot, symbol, 0.0, sl, tp, "PipHive#" + IntegerToString(id));
   else
      ok = trade.Sell(lot, symbol, 0.0, sl, tp, "PipHive#" + IntegerToString(id));

   if(ok)
   {
      ulong ticket = trade.ResultOrder();
      double fill = trade.ResultPrice();
      Print("PipHiveBridge: order ", id, " (", action, " ", symbol, " ", lot, " lots) filled, ticket ", ticket);
      ReportResult(id, "filled", IntegerToString((long)ticket), fill);
   }
   else
   {
      Print("PipHiveBridge: order ", id, " failed to execute, retcode ", trade.ResultRetcode(),
            " (", trade.ResultRetcodeDescription(), ")");
      ReportResult(id, "failed", "", 0.0);
   }
}

//+------------------------------------------------------------------+
void ReportResult(long orderId, string status, string ticket, double fillPrice)
{
   string json = "{\"api_key\":\"" + InpApiKey + "\",\"order_id\":" + IntegerToString((int)orderId) +
                 ",\"status\":\"" + status + "\"";
   if(StringLen(ticket) > 0)
      json += ",\"ticket\":\"" + ticket + "\"";
   if(fillPrice > 0.0)
      json += ",\"fill_price\":" + DoubleToString(fillPrice, 5);
   json += "}";

   uchar data[];
   StringToCharArray(json, data, 0, StringLen(json));
   uchar result[];
   string resultHeaders;

   ResetLastError();
   int status_code = WebRequest("POST", InpApiBaseUrl + "/mt5/result",
                                 "Content-Type: application/json\r\n", 10000, data, result, resultHeaders);
   if(status_code == -1)
      Print("PipHiveBridge: failed to report result for order ", orderId, ", error ", GetLastError());
   else if(status_code != 200)
      Print("PipHiveBridge: POST /mt5/result for order ", orderId, " returned HTTP ", status_code);
}
//+------------------------------------------------------------------+
