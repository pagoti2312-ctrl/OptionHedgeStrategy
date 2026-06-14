from market_data import get_provider

def main():
    provider = get_provider('nse')
    # Get next expiry and option chain
    expiry = provider.get_next_expiry('NIFTY')
    print(f"Using expiry: {expiry}")
    res = provider.get_option_chain('NIFTY', expiry)
    if res.get('s') != 'ok':
        print('Error fetching option chain:', res.get('message'))
        return
    data = res.get('data')
    # nsepython returns option chain structure; try to extract ATM
    from market_data import get_provider


    def main():
        provider = get_provider('nse')
        expiry = provider.get_next_expiry('NIFTY')
        print(f"Using expiry: {expiry}")

        res = provider.get_option_chain('NIFTY', expiry)
        if res.get('s') != 'ok':
            print('Error fetching option chain:', res.get('message'))
            return

        data = res.get('data')
        # Normalize records to a list of rows
        records = None
        if isinstance(data, dict):
            records = data.get('records') or data.get('data') or data
        else:
            records = data

        # Try to extract rows list
        rows = []
        if isinstance(records, dict):
            # common shapes: {'data': [...], 'underlyingValue': x}
            if 'data' in records and isinstance(records['data'], list):
                rows = records['data']
            else:
                # find first list value
                for v in records.values():
                    if isinstance(v, list):
                        rows = v
                        break
        elif isinstance(records, list):
            rows = records

        # Determine underlying spot
        underlying = None
        if isinstance(records, dict):
            underlying = records.get('underlyingValue') or records.get('underlying_value')

        if not underlying:
            q = provider.get_live_quotes(['NIFTY'])
            if q.get('s') == 'ok':
                underlying = q['data'].get('NIFTY', {}).get('ltp')

        print('Underlying spot:', underlying)

        step = 50
        atm = (round(underlying / step) * step) if underlying else None
        print('ATM strike (rounded):', atm)

        if not rows:
            print('No option rows parsed from option chain.')
            return

        # Find ATM row
        atm_row = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            sp = row.get('strikePrice') or row.get('strike') or row.get('strike_price')
            if sp is None:
                continue
            try:
                if atm is not None and int(round(sp)) == int(atm):
                    atm_row = row
                    break
            except Exception:
                continue

        if not atm_row:
            print('ATM row not found in option chain.')
            return

        ce = atm_row.get('CE') or atm_row.get('ce') or atm_row.get('call') or {}
        pe = atm_row.get('PE') or atm_row.get('pe') or atm_row.get('put') or {}

        print('\nATM Option Data:')
        print('Strike:', atm)
        print('CE:', ce)
        print('PE:', pe)


    if __name__ == '__main__':
        main()
