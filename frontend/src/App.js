import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart
} from 'recharts';
import './App.css';

function App() {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [historicalDays, setHistoricalDays] = useState(90);
  const [forecastDays, setForecastDays] = useState(30);
  const [historicalData, setHistoricalData] = useState([]);
  const [forecastData, setForecastData] = useState([]);
  const [accuracyMetrics, setAccuracyMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hiddenSeries, setHiddenSeries] = useState({});

  // Fetch products on mount
  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      const response = await axios.get('/api/products');
      setProducts(response.data);
      if (response.data.length > 0) {
        setSelectedProduct(response.data[0].product_id);
      }
    } catch (err) {
      setError('Failed to fetch products: ' + err.message);
    }
  };

  const fetchHistoricalData = async () => {
    if (!selectedProduct) return;

    try {
      const response = await axios.get('/api/historical', {
        params: {
          product_id: selectedProduct,
          days_back: historicalDays
        }
      });
      setHistoricalData(response.data);
    } catch (err) {
      setError('Failed to fetch historical data: ' + err.message);
    }
  };

  const generateForecast = async () => {
    if (!selectedProduct) return;

    setLoading(true);
    setError('');

    try {
      // Generate forecast
      const response = await axios.post('/api/forecast', {
        product_id: selectedProduct,
        forecast_days: forecastDays
      });
      setForecastData(response.data.forecast);

      // Fetch accuracy metrics
      try {
        const metricsResponse = await axios.get(`/api/accuracy/${selectedProduct}`);
        setAccuracyMetrics(metricsResponse.data);
      } catch (err) {
        console.warn('Could not fetch accuracy metrics:', err.message);
      }

      // Refresh historical data
      await fetchHistoricalData();
    } catch (err) {
      setError('Failed to generate forecast: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLegendClick = (dataKey) => {
    setHiddenSeries(prev => ({
      ...prev,
      [dataKey]: !prev[dataKey]
    }));
  };

  // Combine historical and forecast data for visualization
  const combinedData = [
    ...historicalData.map(d => ({
      date: d.sale_date,
      actual: parseFloat(d.quantity_sold),
      type: 'historical'
    })),
    ...forecastData.map(d => ({
      date: d.forecast_date,
      forecast: parseFloat(d.predicted_quantity),
      lower: parseFloat(d.lower_bound),
      upper: parseFloat(d.upper_bound),
      type: 'forecast'
    }))
  ];

  const selectedProductInfo = products.find(p => p.product_id === parseInt(selectedProduct));

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const formattedDate = label ? label.split('T')[0] : label;
      return (
        <div style={{
          backgroundColor: 'white',
          padding: '10px',
          border: '1px solid #ccc',
          borderRadius: '4px'
        }}>
          <p style={{ margin: '0 0 5px 0', fontWeight: 'bold' }}>{formattedDate}</p>
          {payload.map((entry, index) => {
            if (entry.dataKey === 'actual' && entry.value != null) {
              return (
                <p key={index} style={{ margin: '3px 0', color: entry.color }}>
                  Actual Sales: {entry.value.toFixed(0)} units
                </p>
              );
            }
            if (entry.dataKey === 'forecast' && entry.value != null) {
              return (
                <p key={index} style={{ margin: '3px 0', color: entry.color }}>
                  Forecast: {entry.value.toFixed(0)} units
                </p>
              );
            }
            return null;
          })}
          {payload.find(p => p.dataKey === 'upper') && payload.find(p => p.dataKey === 'lower') && (
            <p style={{ margin: '3px 0', color: '#667eea' }}>
              95% CI: [{payload.find(p => p.dataKey === 'lower').value.toFixed(0)} - {payload.find(p => p.dataKey === 'upper').value.toFixed(0)}] units
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="App">
      <header className="header">
        <h1>Retail Inventory Forecaster</h1>
        <p>ML-powered inventory forecasting with confidence intervals</p>
        <p>To begin, simply choose a product and the amount of historical and forecasted days to present in the graph.</p>
      </header>

      <div className="container">
        {error && <div className="error">{error}</div>}

        <div className="controls">
          <div className="control-row">
            <div className="form-group">
              <label>Product</label>
              <select
                value={selectedProduct}
                onChange={(e) => setSelectedProduct(e.target.value)}
              >
                <option value="">Select a product...</option>
                {products.map(product => (
                  <option key={product.product_id} value={product.product_id}>
                    {product.product_name} - ${product.unit_price}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Historical Days</label>
              <input
                type="number"
                value={historicalDays}
                onChange={(e) => setHistoricalDays(parseInt(e.target.value))}
                min="30"
                max="730"
              />
            </div>

            <div className="form-group">
              <label>Forecast Days</label>
              <input
                type="number"
                value={forecastDays}
                onChange={(e) => setForecastDays(parseInt(e.target.value))}
                min="7"
                max="90"
              />
            </div>

            <button
              className="btn btn-primary"
              onClick={generateForecast}
              disabled={!selectedProduct || loading}
            >
              {loading ? 'Generating...' : 'Generate Forecast'}
            </button>
          </div>
        </div>

        {selectedProductInfo && (
          <div className="info">
            Selected: <strong>{selectedProductInfo.product_name}</strong> |
            Category: {selectedProductInfo.category} |
            Price: ${selectedProductInfo.unit_price}
          </div>
        )}

        {accuracyMetrics && accuracyMetrics.mae != null && accuracyMetrics.mape != null && (
          <div className="metrics">
            <div className="metric-card">
              <h3>Mean Absolute Error</h3>
              <div className="value">
                {!isNaN(accuracyMetrics.mae) ? accuracyMetrics.mae.toFixed(2) : 'N/A'}
                <span className="unit">units</span>
              </div>
            </div>
            <div className="metric-card">
              <h3>Mean Absolute % Error</h3>
              <div className="value">
                {!isNaN(accuracyMetrics.mape) ? accuracyMetrics.mape.toFixed(2) : 'N/A'}
                <span className="unit">%</span>
              </div>
            </div>
          </div>
        )}

        {combinedData.length > 0 && (
          <div className="charts-grid">
            <div className="chart-card">
              <h2>Sales Forecast with Confidence Intervals</h2>
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart data={combinedData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => value ? value.split('T')[0] : value}
                  />
                  <YAxis />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    onClick={(e) => handleLegendClick(e.dataKey)}
                    wrapperStyle={{ cursor: 'pointer' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="upper"
                    stroke="#667eea"
                    strokeWidth={1}
                    fill="#667eea"
                    fillOpacity={0.2}
                    name="95% Confidence Interval"
                    legendType="rect"
                    hide={hiddenSeries['upper']}
                  />
                  <Area
                    type="monotone"
                    dataKey="lower"
                    stroke="none"
                    fill="#ffffff"
                    fillOpacity={1}
                    legendType="none"
                    hide={hiddenSeries['upper']}
                  />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#2196f3"
                    strokeWidth={2}
                    dot={false}
                    name="Actual Sales"
                    legendType="line"
                    hide={hiddenSeries['actual']}
                  />
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke="#667eea"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="Forecasted Sales"
                    legendType="plainline"
                    hide={hiddenSeries['forecast']}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {!loading && combinedData.length === 0 && (
          <div className="chart-card">
            <div className="loading">
              Select a product and click "Generate Forecast" to view predictions
            </div>
          </div>
        )}

        {loading && (
          <div className="chart-card">
            <div className="loading">
              Analyzing historical data and generating forecasts...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
