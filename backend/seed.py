"""Container entrypoint helper: load the dataset into the database.

    python seed.py                 # seeded synthetic dataset (default)
    python seed.py --dataset kaggle --data-dir /data/store-sales
"""
import argparse
import os

from database import init_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', choices=['synthetic', 'kaggle'], default=os.getenv('DATASET', 'synthetic'))
    parser.add_argument('--data-dir', default=os.getenv('KAGGLE_DATA_DIR', '/data/store-sales'))
    args = parser.parse_args()

    init_db()   # idempotent schema + migration
    if args.dataset == 'kaggle':
        from import_kaggle_store_sales import import_store_sales_data
        import_store_sales_data(args.data_dir)
    else:
        from generate_sample_data import generate_sample_data
        generate_sample_data()


if __name__ == '__main__':
    main()
