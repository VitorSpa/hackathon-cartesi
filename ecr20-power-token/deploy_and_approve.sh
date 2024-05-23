#!/bin/bash

RPC_URL="http://localhost:8545"
MNEMONIC="test test test test test test test test test test test junk"
ACCOUNT=0 # account 0 = 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266

ERC20_PORTAL_ADDRESS="0x9C21AEb2093C32DDbC53eEF24B873BDCd1aDa1DB" # from 'cartesi address-book'
DAPP_ADDRESS="0xab7528bb862fb57e8a2bcd567a2e929a0be56a5e" # from 'cartesi address-book'

AMOUNT=10000
AMOUNT_IN_WEI="${AMOUNT}000000000000000000" # 10000 * 10^18

if [ -f "tokenDeploy.json" ]
then
    echo "Token already Deployed, address is $(cat tokenDeploy.json | cut -d "," -f 2 | cut -d ":" -f 2 | cut -d "\"" -f 2)"
    exit 0;
fi

# deploy ERC20 Token
echo "Deploying PowerToken contract..."
docker run -v "./:/opt" --rm --net="host" ghcr.io/foundry-rs/foundry "cd /opt && forge create --rpc-url ${RPC_URL} --mnemonic \"$MNEMONIC\" --mnemonic-index ${ACCOUNT} --json src/PowerToken.sol:PowerToken --constructor-args \"$AMOUNT_IN_WEI\" | tee tokenDeploy.json"

if [ $(wc -c tokenDeploy.json | cut -d " " -f 1) == 0 ]
then
    rm tokenDeploy.json
    echo "Failed to deploy"
    exit 1
fi

# get the address of the deployed Token
TOKEN_ADDRESS=`cat tokenDeploy.json | cut -d "," -f 2 | cut -d ":" -f 2 | cut -d "\"" -f 2`
echo -e "Deployed to ${TOKEN_ADDRESS}\n"

# approve ERC20_Portal (this gives permission for the ERC20_PORTAL to move the assets from the account)
echo "Allowing Portal to move ${AMOUNT} PowerToken..."
docker run --rm --net="host" ghcr.io/foundry-rs/foundry "cast send --mnemonic \"$MNEMONIC\" --mnemonic-index ${ACCOUNT} --rpc-url ${RPC_URL} ${TOKEN_ADDRESS} \"approve(address,uint256)\" ${ERC20_PORTAL_ADDRESS} ${AMOUNT_IN_WEI}"
