import unittest
from production_engine import StrategyEngine

class TestStrategyEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = StrategyEngine()

    def test_analyze_sentiment_positive(self):
        text = "Company reports record breaking profits and excellent growth."
        score = self.strategy.analyze_sentiment(text)
        self.assertGreater(score, 0)

    def test_analyze_sentiment_negative(self):
        text = "Company files for bankruptcy amid massive scandal."
        score = self.strategy.analyze_sentiment(text)
        self.assertLess(score, 0)

    def test_predict_logic(self):
        signal, conf = self.strategy.predict(0.9) 
        self.assertIn(signal, ["BUY", "SELL", "HOLD"])
        self.assertTrue(0 <= conf <= 1)

if __name__ == '__main__':
    unittest.main()
