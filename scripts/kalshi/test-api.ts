import { MarketApi, Configuration } from 'kalshi-typescript';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../..');

// Load API credentials
const apiKeyId = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-public.txt'), 'utf-8').trim();
const privateKeyPath = path.join(rootDir, 'kalshi-api-key-private.txt');

console.log('API Key ID:', apiKeyId);
console.log('Private Key Path:', privateKeyPath);

// Configure the API client
const configuration = new Configuration({
    apiKey: apiKeyId,
    privateKeyPath: privateKeyPath
});

const marketApi = new MarketApi(configuration);

async function testGetMarkets() {
    console.log('\n--- Testing getMarkets (list all markets) ---');
    try {
        const { status, data } = await marketApi.getMarkets(
            10,        // limit - just get 10 markets
            undefined, // cursor
            undefined, // eventTicker
            undefined, // seriesTicker
            undefined, // minCreatedTs
            undefined, // maxCreatedTs
            undefined, // maxCloseTs
            undefined, // minCloseTs
            undefined, // minSettledTs
            undefined, // maxSettledTs
            'open',    // status - only open markets
            undefined, // tickers
            undefined  // mveFilter
        );
        console.log('Status:', status);
        console.log('Number of markets:', data.markets?.length);
        
        // Print first market in detail
        if (data.markets && data.markets.length > 0) {
            console.log('\nFirst market (full details):');
            console.log(JSON.stringify(data.markets[0], null, 2));
            
            // Return a market for candlestick testing
            return data.markets[0];
        }
    } catch (error: any) {
        console.error('Error:', error.message || error);
        if (error.response) {
            console.error('Response status:', error.response.status);
            console.error('Response data:', JSON.stringify(error.response.data, null, 2));
        }
    }
    return null;
}

async function testGetMarketCandlesticks(seriesTicker: string, marketTicker: string) {
    console.log(`\n--- Testing getMarketCandlesticks ---`);
    console.log(`Series: ${seriesTicker}, Market: ${marketTicker}`);
    
    try {
        const endTs = Math.floor(Date.now() / 1000);
        const startTs = endTs - (7 * 24 * 60 * 60); // 7 days ago
        
        // periodInterval: 1 (1 minute), 60 (1 hour), 1440 (1 day)
        const { status, data } = await marketApi.getMarketCandlesticks(
            seriesTicker,
            marketTicker,
            startTs,
            endTs,
            60  // 1 hour intervals
        );
        
        console.log('Status:', status);
        console.log('Number of candlesticks:', data.candlesticks?.length || 0);
        
        if (data.candlesticks && data.candlesticks.length > 0) {
            // Print first few candlesticks with ALL fields
            console.log('\nFirst 3 candlesticks (raw):');
            data.candlesticks.slice(0, 3).forEach((candle: any, i: number) => {
                console.log(`\n${i + 1}. Full object:`);
                console.log(JSON.stringify(candle, null, 2));
            });
        }
    } catch (error: any) {
        console.error('Error:', error.message || error);
        if (error.response) {
            console.error('Response status:', error.response.status);
            console.error('Response data:', JSON.stringify(error.response.data, null, 2));
        }
    }
}

async function testGetTrades() {
    console.log('\n--- Testing getTrades ---');
    try {
        const { status, data } = await marketApi.getTrades(
            5,        // limit
            undefined, // cursor
            undefined, // ticker
            undefined, // minTs
            undefined  // maxTs
        );
        console.log('Status:', status);
        console.log('Number of trades:', data.trades?.length);
        
        if (data.trades && data.trades.length > 0) {
            console.log('\nFirst trade (full details):');
            console.log(JSON.stringify(data.trades[0], null, 2));
        }
    } catch (error: any) {
        console.error('Error:', error.message || error);
        if (error.response) {
            console.error('Response status:', error.response.status);
            console.error('Response data:', JSON.stringify(error.response.data, null, 2));
        }
    }
}

// Also search for NBA-related markets
async function searchNBAMarkets() {
    console.log('\n--- Searching for NBA markets ---');
    try {
        const { status, data } = await marketApi.getMarkets(
            20,        // limit
            undefined, // cursor
            undefined, // eventTicker
            'KXNBAGAME', // seriesTicker - NBA games
            undefined, // minCreatedTs
            undefined, // maxCreatedTs
            undefined, // maxCloseTs
            undefined, // minCloseTs
            undefined, // minSettledTs
            undefined, // maxSettledTs
            'open',    // status
            undefined, // tickers
            undefined  // mveFilter
        );
        console.log('Status:', status);
        console.log('Number of NBA markets:', data.markets?.length);
        
        if (data.markets && data.markets.length > 0) {
            console.log('\nNBA Markets:');
            data.markets.forEach((market: any, i: number) => {
                console.log(`${i + 1}. ${market.ticker}: ${market.title}`);
                console.log(`   Yes: ${market.yes_bid}¢-${market.yes_ask}¢, Volume: ${market.volume}`);
            });
            return data.markets[0];
        }
    } catch (error: any) {
        console.error('Error:', error.message || error);
        if (error.response) {
            console.error('Response status:', error.response.status);
            console.error('Response data:', JSON.stringify(error.response.data, null, 2));
        }
    }
    return null;
}

async function main() {
    console.log('=== Kalshi API Test ===\n');
    
    // Test getTrades
    await testGetTrades();
    
    // Test getMarkets
    const market = await testGetMarkets();
    
    // Search NBA markets (interesting for your project!)
    const nbaMarket = await searchNBAMarkets();
    
    // Test candlesticks on NBA market if found
    if (nbaMarket) {
        const seriesTicker = 'KXNBAGAME';
        await testGetMarketCandlesticks(seriesTicker, nbaMarket.ticker);
    } else if (market) {
        const seriesTicker = market.ticker.split('-')[0];
        await testGetMarketCandlesticks(seriesTicker, market.ticker);
    }
}

main().catch(console.error);
