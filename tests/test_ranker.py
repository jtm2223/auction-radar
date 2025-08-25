"""Tests for lot ranking system."""

import pytest
from auction_radar.ranker import lot_ranker

class TestLotRanker:
    """Test lot ranking functionality."""
    
    def test_score_land_cruiser(self):
        """Test scoring of Land Cruiser (highest priority)."""
        lot = {
            'make': 'Toyota',
            'model': 'Land Cruiser',
            'raw_text': '2018 Toyota Land Cruiser Heritage Edition',
            'title_status': 'clean',
            'year': 2018
        }
        
        score = lot_ranker.score_lot(lot)
        assert score > 0.8, f"Land Cruiser should score high, got {score}"
    
    def test_score_fourrunner(self):
        """Test scoring of 4Runner."""
        lot = {
            'make': 'Toyota',
            'model': '4Runner',
            'raw_text': '2019 Toyota 4Runner TRD Pro',
            'title_status': 'clean',
            'year': 2019
        }
        
        score = lot_ranker.score_lot(lot)
        assert 0.7 < score < 1.0, f"4Runner should score well, got {score}"
    
    def test_title_status_penalties(self):
        """Test that title status affects scoring."""
        base_lot = {
            'make': 'Toyota',
            'model': 'Tacoma',
            'raw_text': '2018 Toyota Tacoma',
            'year': 2018
        }
        
        # Test different title statuses
        clean_lot = {**base_lot, 'title_status': 'clean'}
        salvage_lot = {**base_lot, 'title_status': 'salvage'}
        parts_lot = {**base_lot, 'title_status': 'parts_only'}
        
        clean_score = lot_ranker.score_lot(clean_lot)
        salvage_score = lot_ranker.score_lot(salvage_lot)
        parts_score = lot_ranker.score_lot(parts_lot)
        
        assert clean_score > salvage_score, "Clean title should score higher than salvage"
        assert salvage_score > parts_score, "Salvage should score higher than parts only"
        assert parts_score > 0, "Parts only should still have some score"
    
    def test_age_penalties(self):
        """Test that vehicle age affects scoring."""
        base_lot = {
            'make': 'Toyota',
            'model': 'Tacoma',
            'raw_text': '2018 Toyota Tacoma',
            'title_status': 'clean'
        }
        
        new_lot = {**base_lot, 'year': 2022}
        old_lot = {**base_lot, 'year': 2010}
        
        new_score = lot_ranker.score_lot(new_lot)
        old_score = lot_ranker.score_lot(old_lot)
        
        assert new_score > old_score, "Newer vehicle should score higher than older"
    
    def test_non_target_vehicles(self):
        """Test that non-target vehicles get zero score."""
        non_target_lot = {
            'make': 'Honda',
            'model': 'Civic',
            'raw_text': '2018 Honda Civic EX',
            'title_status': 'clean',
            'year': 2018
        }
        
        score = lot_ranker.score_lot(non_target_lot)
        assert score == 0, "Non-target vehicle should score 0"
    
    def test_vin_deduplication(self):
        """Test VIN deduplication functionality."""
        lots = [
            {
                'vin': '1ABCD23EFGH456789',
                'make': 'Toyota',
                'model': 'Tacoma',
                'raw_text': '2018 Toyota Tacoma',
                'title_status': 'clean',
                'year': 2018,
                'score': 0.8
            },
            {
                'vin': '1ABCD23EFGH456789',  # Same VIN
                'make': 'Toyota',
                'model': 'Tacoma',
                'raw_text': '2018 Toyota Tacoma',
                'title_status': 'salvage',  # Worse condition
                'year': 2018,
                'score': 0.6
            },
            {
                'vin': '2WXYZ98KLMN123456',  # Different VIN
                'make': 'Nissan',
                'model': 'Frontier',
                'raw_text': '2019 Nissan Frontier',
                'title_status': 'clean',
                'year': 2019,
                'score': 0.7
            }
        ]
        
        deduped = lot_ranker._deduplicate_by_vin(lots)
        
        # Should have 2 lots (one duplicate removed)
        assert len(deduped) == 2
        
        # Should keep the higher scoring one
        tacoma_lots = [lot for lot in deduped if lot['vin'] == '1ABCD23EFGH456789']
        assert len(tacoma_lots) == 1
        assert tacoma_lots[0]['score'] == 0.8
    
    def test_rank_lots(self):
        """Test full lot ranking process."""
        lots = [
            {
                'make': 'Honda',
                'model': 'Civic',
                'raw_text': '2018 Honda Civic',
                'title_status': 'clean',
                'year': 2018
            },
            {
                'make': 'Toyota',
                'model': 'Land Cruiser',
                'raw_text': '2018 Toyota Land Cruiser',
                'title_status': 'clean',
                'year': 2018
            },
            {
                'make': 'Toyota',
                'model': '4Runner',
                'raw_text': '2019 Toyota 4Runner',
                'title_status': 'salvage',
                'year': 2019
            }
        ]
        
        ranked = lot_ranker.rank_lots(lots)
        
        # Should only include target vehicles (exclude Civic)
        assert len(ranked) == 2
        
        # Should be sorted by score (highest first)
        assert ranked[0]['score'] >= ranked[1]['score']
        
        # Land Cruiser should typically rank higher
        land_cruiser = next((lot for lot in ranked if 'cruiser' in lot.get('raw_text', '').lower()), None)
        assert land_cruiser is not None
        assert land_cruiser == ranked[0], "Land Cruiser should rank first"